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
    this.UPLOAD_ENDPOINT = "/api/v1/upload_url";
    this.LIST_URLS_ENDPOINT = "/api/v1/list_urls";
    this.DELETE_URL_ENDPOINT = "/api/v1/delete_url";
    this.http_prefix = "http://";
    this.JSON_HTTP_HEADER_VALUE = "application/json";
    this.HTTP_POST_METHOD = "POST";
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
  upload_url(web_page_url, callback) {
    // Request body format.
    let upload_url = {
      url: web_page_url,
    };
    let endpoint_url =
      this.http_prefix + window.location.host + this.UPLOAD_ENDPOINT;

    this.dispatch_fetch_start_event();
    return fetch(endpoint_url, {
      method: this.HTTP_POST_METHOD,
      headers: {
        "Content-Type": this.JSON_HTTP_HEADER_VALUE,
        "X-CSRFToken": this.csrfToken,
      },
      body: JSON.stringify(upload_url),
    })
      .then((response) => response.json())
      .then((upload) => {
        this.uploads.push(upload);
        this.dispatch_fetch_end_event();
        this.dispatch_render_uploads_event();
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
   * Checks status of each in progress upload.
   */
  check_statuses() {
    for (let i = 0; i < this.uploads.length; i++) {
      let upload = this.uploads[i];
      if (upload.status != "IN_PROGRESS") {
        continue;
      }

      let endpoint_url =
        this.http_prefix +
        window.location.host +
        this.UPLOAD_ENDPOINT +
        "?id=" +
        upload.id;

      this.dispatch_fetch_start_event();
      fetch(endpoint_url)
        .then((response) => response.json())
        .then((data) => {
          this.dispatch_fetch_end_event();
          console.log("data status: " + data.status);
        })
        .catch((error) => {
          this.dispatch_fetch_end_event();
          throw error;
        });
    }
  }

  /**
   * List URLs associated with the given user's org.
   */
  list_urls() {
    let endpoint_url =
      this.http_prefix + window.location.host + this.LIST_URLS_ENDPOINT;

    this.dispatch_fetch_start_event();
    fetch(endpoint_url)
      .then((response) => response.json())
      .then((data) => {
        this.dispatch_fetch_end_event();
        if (!("uploads" in data)) {
          throw new Error("Invalid Uploads response format");
        }
        this.uploads = data.uploads;
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
    let endpoint_url = `${this.http_prefix}${window.location.host}${this.DELETE_URL_ENDPOINT}?id=${upload.id}`;

    this.dispatch_fetch_start_event();
    fetch(endpoint_url)
      .then((response) => response.json())
      .then((data) => {
        // Remove element from uploads list since it is deleted now.
        const index = this.uploads.indexOf(upload);
        if (index > -1) {
          this.uploads.splice(index, 1);
        }
        this.dispatch_fetch_end_event();
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
}
