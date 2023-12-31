import {
  PROTOCOL_PREFIX,
  JSON_HTTP_HEADER_VALUE,
  HTTP_POST_METHOD,
  HTTP_DELETE_METHOD,
  checkErrorCode,
} from "./constants.js";

export class APIKeyService extends EventTarget {
  /**
   * Service to manage creation, deletion and fetching of API key for given organization.
   * @param {string} csrfToken
   */
  constructor(csrfToken) {
    super();
    this.csrfToken = csrfToken;
    this.api_key = null;

    // Constants.
    this.API_KEY_ENDPOINT = "/api/v1/api-key";
  }

  /**
   * Return API key object or null if no key exists.
   * @returns API key or null.
   */
  get_api_key() {
    return this.api_key;
  }

  /**
   * Fetch existing API Key.
   */
  fetch_api_key() {
    let endpoint_url = `${PROTOCOL_PREFIX}${window.location.host}${this.API_KEY_ENDPOINT}`;

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
        checkErrorCode(data);

        if (!("key" in data)) {
          throw new Error("Invalid API Key response format");
        }
        if (data.key === "") {
          // API Key does not exist.
          this.dispatch_api_key_render_creation();
          return;
        }

        this.api_key = data.key;
        this.dispatch_api_key_render_existing();
      })
      .catch((error) => {
        this.dispatch_fetch_end_event();
        throw error;
      });
  }

  /**
   * Create API Key.
   */
  create_api_key() {
    let endpoint_url = `${PROTOCOL_PREFIX}${window.location.host}${this.API_KEY_ENDPOINT}`;

    this.dispatch_fetch_start_event();
    return fetch(endpoint_url, {
      method: HTTP_POST_METHOD,
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
        checkErrorCode(data);
        if (!("key" in data) || !("raw_value" in data)) {
          throw new Error("Invalid API Key response format");
        }
        alert(
          `This is your API key: ${data.raw_value}\n\nPlease save this somewhere safe, you will not be shown it again.`
        );
        this.api_key = data.key;
        this.dispatch_api_key_render_existing();
      })
      .catch((error) => {
        this.dispatch_fetch_end_event();
        throw error;
      });
  }

  /**
   * Deletes API key.
   */
  delete_api_key() {
    let endpoint_url = `${PROTOCOL_PREFIX}${window.location.host}${this.API_KEY_ENDPOINT}`;

    this.dispatch_fetch_start_event();
    return fetch(endpoint_url, {
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
        checkErrorCode(data);

        this.dispatch_api_key_render_creation();
      })
      .catch((error) => {
        this.dispatch_fetch_end_event();
        throw error;
      });
  }

  /**
   * Helper to dispatch api_key_render_creation event.
   */
  dispatch_api_key_render_creation() {
    this.dispatchEvent(new Event("api_key_render_creation"));
  }

  /**
   * Helper to dispatch api_key_render_existing event.
   */
  dispatch_api_key_render_existing() {
    this.dispatchEvent(new Event("api_key_render_existing"));
  }

  /**
   * Helper to dispatch api_key_fetch_start event.
   */
  dispatch_fetch_start_event() {
    this.dispatchEvent(new Event("api_key_fetch_start"));
  }

  /**
   * Helper to dispatch api_key_fetch_complete event.
   */
  dispatch_fetch_end_event() {
    this.dispatchEvent(new Event("api_key_fetch_complete"));
  }
}
