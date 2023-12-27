export class UploadURLService {
  /**
   * Service that uploads and fetches data related to URLs.
   * Separation from the view that listens to events and performs DOM manipulation.
   * The CSRF Token is used to send POST requests to the server.
   * @param {string} csrfToken
   */
  constructor(csrfToken) {
    this.csrfToken = csrfToken;
    this.uploads = [];

    // Constants.
    this.UPLOAD_ENDPOINT = "/api/v1/upload_url";
    this.http_prefix = "http://";
    this.JSON_HTTP_HEADER_VALUE = "application/json";
    this.HTTP_POST_METHOD = "POST";
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
      this.http_prefix + window.location.host + this.UPLOAD_ENDPOINT;

    return fetch(endpoint_url, {
      method: this.HTTP_POST_METHOD,
      headers: {
        "Content-Type": this.JSON_HTTP_HEADER_VALUE,
        "X-CSRFToken": this.csrfToken,
      },
      body: JSON.stringify(upload_url),
    }).then((response) => response.json());
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

      fetch(endpoint_url)
        .then((response) => response.json())
        .then((data) => {
          console.log("data status: " + data.status);
        });
    }
  }
}
