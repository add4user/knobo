export class UploadURL {
  constructor() {
    this.uploadButton = document.querySelector("#upload-url-btn");
    this.uploadButton.addEventListener(
      "click",
      this.handleUploadButtonBlick.bind(this)
    );
    this.uploadInput = document.querySelector("#upload-url-input");
    this.uploadsList = document.querySelector("#uploads-list");
    this.csrfToken = document.querySelector("#upload_url_csrf_token").value;

    // Remove when not debugging.
    this.debug = true;

    if (this.debug) {
      this.addUploadToList(
        "https://flask.palletsprojects.com/en/3.0.x/extensions/"
      );
      this.uploadsList.classList.remove("hidden");
    }
  }

  handleUploadButtonBlick(event) {
    if (this.uploadInput.value === "") {
      alert("URL cannot be empty");
      return;
    }
    let page_url = this.uploadInput.value;
    let upload_url = {
      url: page_url,
    };

    this.addUploadToList(page_url);
    if (this.uploadsList.classList.contains("hidden")) {
      this.uploadsList.classList.remove("hidden");
    }
    this.uploadInput.value = "";

    if (this.debug) {
      // Don't call server when debugging.
      return;
    }

    let host = window.location.host;
    let url = "http://" + host + "/api/v1/upload_url";
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this.csrfToken,
      },
      body: JSON.stringify(upload_url),
    });
  }

  addUploadToList(url) {
    /**
     * Add given URL to list of uploaded URLs.
     */
    let ol = this.uploadsList.querySelector("ol");

    let li = document.createElement("li");

    // Create serial number.
    let snum = document.createElement("p");
    snum.innerText = (ol.childElementCount + 1).toString() + ".";
    snum.classList.add("upload-snum");
    li.appendChild(snum);

    // Create link
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
    p.innerText = "Upload In Progress";
    p.classList.add("upload-status");
    li.appendChild(p);

    // Add delete Button.
    let b = document.createElement("button");
    b.innerText = "Delete";
    li.appendChild(b);

    ol.appendChild(li);
  }
}
