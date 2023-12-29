import { UploadURLService } from "./upload_url_service.js";

export class UploadURL {
  /**
   * View to allow user to upload and manage uploaded URLs.
   */
  constructor() {
    this.uploadButton = document.querySelector("#upload-url-btn");
    this.uploadButton.addEventListener(
      "click",
      this.handleUploadButtonClick.bind(this)
    );
    this.uploadInput = document.querySelector("#upload-url-input");
    this.uploadsList = document.querySelector("#uploads-list");

    let csrfToken = document.querySelector("#upload_url_csrf_token").value;
    this.loader = document.querySelector(".loader");

    this.uploadURLService = new UploadURLService(csrfToken);

    this.uploadURLService.addEventListener(
      "render_uploads",
      this.renderUploads.bind(this)
    );

    this.uploadURLService.addEventListener("fetch_start", () =>
      this.showLoader()
    );

    this.uploadURLService.addEventListener("fetch_complete", () =>
      this.hideLoader()
    );

    // Fetch already uploaded URLs.
    this.uploadURLService.list_urls();
  }

  /**
   * render all uploaded URLs.
   */
  renderUploads() {
    let uploads = this.uploadURLService.getUploads();

    // Replace all children of existing list with current uploads.
    let ol = this.uploadsList.querySelector("ol");
    var uploadHTMLArr = [];
    for (let i = 0; i < uploads.length; i++) {
      let upload = uploads[i];
      let li = this.createUploadHTML(i, upload);
      uploadHTMLArr.push(li);
    }
    ol.replaceChildren(...uploadHTMLArr);

    if (uploads.length > 0) {
      this.unhideUploadsList();
    } else {
      this.hideUploadsList();
    }
    this.clearUploadInput();
  }

  /**
   * Handles upload button click by calling server to upload URL.
   * @param {Event} event
   */
  handleUploadButtonClick(event) {
    if (this.uploadInput.value === "") {
      alert("URL cannot be empty");
      return;
    }
    let page_url = this.uploadInput.value;
    this.uploadURLService.upload_url(page_url);
  }

  /**
   * Returns HTML for upload (as a list item) using index and upload object as inputs.
   * @param {Object} index
   * @param {Object} upload
   */
  createUploadHTML(index, upload) {
    let li = document.createElement("li");

    // Create serial number.
    let snum = document.createElement("p");
    snum.innerText = (index + 1).toString() + ".";
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
    b.addEventListener("click", () => this.uploadURLService.delete_url(upload));
    li.appendChild(b);

    return li;
  }

  /**
   * UnHides uploads list if hidden currently.
   */
  unhideUploadsList() {
    if (this.uploadsList.classList.contains("hidden")) {
      this.uploadsList.classList.remove("hidden");
    }
  }

  /**
   * Hides Upload list if unhidden currently.
   */
  hideUploadsList() {
    if (!this.uploadsList.classList.contains("hidden")) {
      this.uploadsList.classList.add("hidden");
    }
  }

  /**
   * Clears upload URL value.
   */
  clearUploadInput() {
    this.uploadInput.value = "";
  }

  /**
   * Show spinning loader.
   */
  showLoader() {
    this.loader.classList.remove("hidden");
  }

  /**
   * Hide spinning loader.
   */
  hideLoader() {
    this.loader.classList.add("hidden");
  }
}
