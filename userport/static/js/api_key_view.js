import { APIKeyService } from "./api_key_service.js";

export class APIKeyView {
  constructor() {
    this.apiKeyDetailsBox = document.querySelector("#api-key-details");
    this.csrfToken = document.querySelector("#api-key-csrf-token").value;
    this.loader = document.querySelector(".loader");

    this.apiKeyService = new APIKeyService(this.csrfToken);
    this.apiKeyService.addEventListener(
      "api_key_render_creation",
      this.addCreateAPIKeyButton.bind(this)
    );

    this.apiKeyService.addEventListener(
      "api_key_render_existing",
      this.renderExistingKey.bind(this)
    );

    this.apiKeyService.addEventListener("api_key_fetch_start", () =>
      this.showLoader()
    );

    this.apiKeyService.addEventListener("api_key_fetch_complete", () =>
      this.hideLoader()
    );

    this.apiKeyService.fetch_api_key();
  }

  /**
   * Add Create API Key Button to the view.
   */
  addCreateAPIKeyButton() {
    this.removeAllChildNodes(this.apiKeyDetailsBox);

    let createBtn = document.createElement("button");
    createBtn.innerText = "Create API Key";
    createBtn.classList.add("create-api-key-btn");
    createBtn.addEventListener(
      "click",
      this.apiKeyService.create_api_key.bind(this.apiKeyService)
    );
    this.apiKeyDetailsBox.appendChild(createBtn);
  }

  /**
   * Display existing API key in the view.
   */
  renderExistingKey() {
    let apiKey = this.apiKeyService.get_api_key();
    if (apiKey === null) {
      throw Error("Expected API Key to not be null");
    }
    this.removeAllChildNodes(this.apiKeyDetailsBox);

    let h4 = document.createElement("h4");
    h4.innerText = "Current API Key: ";
    let span = document.createElement("span");
    span.innerText = this.keyObfuscatedFormat(apiKey);
    h4.appendChild(span);
    this.apiKeyDetailsBox.appendChild(h4);

    let deleteButton = document.createElement("button");
    deleteButton.innerText = "Delete Key";
    deleteButton.classList.add("delete-api-key-btn");
    deleteButton.addEventListener(
      "click",
      this.apiKeyService.delete_api_key.bind(this.apiKeyService)
    );
    this.apiKeyDetailsBox.appendChild(deleteButton);
  }

  /**
   * Return obfuscated format of key to display in the view.
   *
   * @param {object} apiKey
   * @returns String representation of the key prefix.
   */
  keyObfuscatedFormat(apiKey) {
    let repeatChar = "*";
    return `${apiKey.key_prefix}${repeatChar.repeat(11)}`;
  }

  /**
   * Remove all children of given parent node.
   * @param {HTMLElement} parent
   */
  removeAllChildNodes(parent) {
    while (parent.firstChild) {
      parent.removeChild(parent.firstChild);
    }
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
