import { UploadURLService } from "./upload_url_service.js";

export class UploadURL {
  constructor() {
    this.uploadButton = document.querySelector("#upload-url-btn");
    this.uploadButton.addEventListener(
      "click",
      this.handleUploadButtonBlick.bind(this)
    );
    this.uploadInput = document.querySelector("#upload-url-input");
    this.uploadsList = document.querySelector("#uploads-list");

    let csrfToken = document.querySelector("#upload_url_csrf_token").value;
    this.uploadURLService = new UploadURLService(csrfToken);
  }

  /**
   * Handles upload button click by calling server to upload URL.
   * @param {Event} event
   */
  handleUploadButtonBlick(event) {
    if (this.uploadInput.value === "") {
      alert("URL cannot be empty");
      return;
    }

    let page_url = this.uploadInput.value;
    this.uploadURLService
      .upload_url(page_url)
      .then(this.handleUploadResponse.bind(this));
  }

  /**
   * Handle result from Upload call to the server.
   */
  handleUploadResponse(upload) {
    // Update data service with upload result.
    this.uploadURLService.addToUploads(upload);

    // Update UI with latest upload result.
    this.addUploadToListView(upload);
    if (this.uploadsList.classList.contains("hidden")) {
      this.uploadsList.classList.remove("hidden");
    }
    this.uploadInput.value = "";
  }

  /**
   * Add upload object to upload object views.
   * @param {Object} upload
   */
  addUploadToListView(upload) {
    let ol = this.uploadsList.querySelector("ol");

    let li = document.createElement("li");

    // Create serial number.
    let snum = document.createElement("p");
    snum.innerText = (ol.childElementCount + 1).toString() + ".";
    snum.classList.add("upload-snum");
    li.appendChild(snum);

    // Create link
    let url = upload.url;
    let adiv = document.createElement("div");
    adiv.classList.add("uploaded-link-container");
    let a = document.createElement("a");
    a.setAttribute("href", url);
    a.setAttribute("target", "_blank");
    let text = document.createTextNode(url);
    a.appendChild(text);
    adiv.appendChild(a);
    li.appendChild(adiv);

    // Create upload status.
    let p = document.createElement("p");
    p.innerText = this.uploadURLService.get_status(upload);
    p.classList.add("upload-status");
    li.appendChild(p);

    // Add delete Button.
    let b = document.createElement("button");
    b.innerText = "Delete";
    li.appendChild(b);

    ol.appendChild(li);
  }
}
