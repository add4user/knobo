import { UserAccount } from "./user_account.js";
import { UploadURL } from "./upload_url.js";

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

  new UserAccount();
  new UploadURL();
}

main();
