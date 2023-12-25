export class UploadURL {
  constructor() {
    this.uploadButton = document.querySelector("#upload-url-btn");
    this.uploadButton.addEventListener(
      "click",
      this.handleUploadButtonBlick.bind(this)
    );
    this.csrfToken = document.querySelector("#upload_url_csrf_token").value;
  }

  handleUploadButtonBlick(event) {
    let upload_url = {
      url: "https://support.atlassian.com/jira-software-cloud/docs/navigate-to-your-work/",
    };

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
}
