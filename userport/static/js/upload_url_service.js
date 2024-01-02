import {
  PROTOCOL_PREFIX,
  JSON_HTTP_HEADER_VALUE,
  HTTP_POST_METHOD,
  HTTP_DELETE_METHOD,
} from "./constants.js";

export class UploadURLService extends EventTarget {
  /**
   * Service that uploads and fetches data related to URLs.
   * Separation from the view that listens to events and performs DOM manipulation.
   * The CSRF Token is used to send POST requests to the server.
   *
   * We extend EventTarget so that the view can listen to data updated events
   * and re-render the views.
   * @param {string} csrfToken
   */
  constructor(csrfToken) {
    super();
    this.csrfToken = csrfToken;
    this.uploads = [];

    // Constants.
    this.URL_ENDPOINT = "/api/v1/url";
    this.URLS_ENDPOINT = "/api/v1/urls";
  }

  /**
   * @returns list of all uploads in the org.
   */
  getUploads() {
    return this.uploads;
  }

  /**
   * Upload given web page URL to the server and returns a promise.
   * @param {string} url
   * @returns {Promise} Promise of the completed upload.
   */
  upload_url(web_page_url) {
    // Request body format.
    let upload_url = {
      url: web_page_url,
    };
    let endpoint_url =
      PROTOCOL_PREFIX + window.location.host + this.URL_ENDPOINT;

    this.dispatch_fetch_start_event();
    return fetch(endpoint_url, {
      method: HTTP_POST_METHOD,
      headers: {
        "Content-Type": JSON_HTTP_HEADER_VALUE,
        "X-CSRFToken": this.csrfToken,
      },
      body: JSON.stringify(upload_url),
    })
      .then((response) =>
        response.json().catch((error) => {
          // Server returned a non JSON response.
          throw new Error(`${response.status}: Server error`);
        })
      )
      .then((upload) => {
        this.dispatch_fetch_end_event();
        this.checkErrorCode(upload);

        this.uploads.push(upload);
        this.dispatch_render_uploads_event();

        // Start checking status for this upload.
        this.check_status(upload.id);
      })
      .catch((error) => {
        this.dispatch_fetch_end_event();
        throw error;
      });
  }

  /**
   * Add Upload object to list of uploads.
   * @param {Object} upload
   */
  addToUploads(upload) {
    this.uploads.push(upload);
  }

  /**
   * Returns status to be displayed from given upload object.
   * @param {Object} upload
   */
  get_status(upload) {
    switch (upload.status) {
      case "IN_PROGRESS":
        return "Upload in progress";
      case "FAILED":
        return "Upload failed";
      case "COMPLETE":
        return "Upload complete";
    }
  }

  /**
   * Returns true if upload is in progress.
   * @param {object} upload
   * @returns boolean
   */
  is_upload_in_progress(upload) {
    return upload.status === "IN_PROGRESS";
  }

  /**
   * Returns true if upload is complete else false.
   * @param {object} upload
   * @returns boolean
   */
  is_upload_complete(upload) {
    return upload.status === "COMPLETE";
  }

  /**
   * Returns true if upload has failed else false.
   * @param {object} upload
   * @returns boolean
   */
  has_upload_failed(upload) {
    return upload.status === "FAILED";
  }

  /**
   * Check status of the upload periodically.
   * @param {string} upload_id
   */
  check_status(upload_id) {
    let endpoint_url = `${PROTOCOL_PREFIX}${window.location.host}${this.URL_ENDPOINT}?id=${upload_id}`;

    fetch(endpoint_url)
      .then((response) =>
        response.json().catch((error) => {
          // Server returned a non JSON response.
          throw new Error(`${response.status}: Server error`);
        })
      )
      .then((upload) => {
        this.checkErrorCode(upload);
        if (upload.status != "IN_PROGRESS") {
          // Polling complete.
          let index = this.uploads.findIndex(
            (existingUpload) => existingUpload.id === upload.id
          );
          if (index == -1) {
            alert(`Uploaded URL ${upload.id} not found in existing uploads`);
          }
          this.uploads[index] = upload;
          this.dispatch_render_uploads_event();
        } else {
          // Continue polling after fixed interval of 20s.
          setTimeout(this.check_status.bind(this), 20000, upload_id);
        }
      })
      .catch((error) => {
        throw error;
      });
  }

  /**
   * List URLs associated with the given user's org.
   */
  list_urls() {
    let endpoint_url =
      PROTOCOL_PREFIX + window.location.host + this.URLS_ENDPOINT;

    this.dispatch_fetch_start_event();
    fetch(endpoint_url)
      .then((response) =>
        response.json().catch((error) => {
          // Server returned a non JSON response.
          throw new Error(`${response.status}: Server error`);
        })
      )
      .then((data) => {
        this.dispatch_fetch_end_event();
        this.checkErrorCode(data);

        if (!("uploads" in data)) {
          throw new Error("Invalid Uploads response format");
        }
        this.uploads = data.uploads;
        for (let i = 0; i < this.uploads.length; i++) {
          // Start checking status for this upload.
          this.check_status(this.uploads[i].id);
        }
        this.dispatch_render_uploads_event();
      })
      .catch((error) => {
        this.dispatch_fetch_end_event();
        throw error;
      });
  }

  /**
   * Delete given upload URL.
   */
  delete_url(upload) {
    let endpoint_url = `${PROTOCOL_PREFIX}${window.location.host}${this.URL_ENDPOINT}?id=${upload.id}`;

    this.dispatch_fetch_start_event();
    fetch(endpoint_url, {
      method: HTTP_DELETE_METHOD,
      headers: {
        "Content-Type": JSON_HTTP_HEADER_VALUE,
        "X-CSRFToken": this.csrfToken,
      },
    })
      .then((response) =>
        response.json().catch((error) => {
          // Server returned a non JSON response.
          throw new Error(`${response.status}: Server error`);
        })
      )
      .then((data) => {
        this.dispatch_fetch_end_event();
        this.checkErrorCode(data);

        // Remove element from uploads list since it is deleted now.
        const index = this.uploads.indexOf(upload);
        if (index > -1) {
          this.uploads.splice(index, 1);
        }
        this.dispatch_render_uploads_event();
      })
      .catch((error) => {
        this.dispatch_fetch_end_event();
        throw error;
      });
  }

  /**
   * Helper to dispatch render_uploads event.
   */
  dispatch_render_uploads_event() {
    this.dispatchEvent(new Event("render_uploads"));
  }

  /**
   * Helper to dispatch fetch_start event.
   */
  dispatch_fetch_start_event() {
    this.dispatchEvent(new Event("fetch_start"));
  }

  /**
   * Helper to dispatch fetch_complete event.
   */
  dispatch_fetch_end_event() {
    this.dispatchEvent(new Event("fetch_complete"));
  }

  /**
   * check if error code is in response data and throws appropriate error if so.
   * @param {object} data Response object
   */
  checkErrorCode(data) {
    if (!("error_code" in data)) {
      return;
    }
    if ("message" in data) {
      throw new Error(`${data.error_code}: ${data.message}`);
    }
  }
}
