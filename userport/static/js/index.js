import { LoggedInBaseView } from "./logged_in_base.js";
import { UploadURL } from "./upload_url.js";
import { APIKeyView } from "./api_key_view.js";

function main() {
  /**
   * Global handler for uncaught exceptions tracked by JS engine on browsers
   * per https://javascript.info/promise-error-handling.
   * We just throw an alert for now.
   */
  window.addEventListener("unhandledrejection", function (event) {
    // the event object has two special properties:
    alert(event.reason); // Error: Whoops! - the unhandled error object
  });

  let route = window.location.pathname;
  switch (route) {
    case "/":
      new LoggedInBaseView();
      new UploadURL();
      break;
    case "/api-key":
      new LoggedInBaseView();
      new APIKeyView();
      break;
  }
}

main();
