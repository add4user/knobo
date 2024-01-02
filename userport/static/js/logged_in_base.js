import { ChatService, ChatState } from "./chat_service.js";

export class LoggedInBaseView {
  /**
   * Contains logic associated with the common logged in view of the user.
   */
  constructor() {
    this.userAccountContainer = document.querySelector("#user-account");
    this.userAccountContainer.addEventListener(
      "click",
      this.handleUserAccountClick.bind(this)
    );
    this.dropDownContent = document.querySelector(
      ".user-account-dropdown-content"
    );

    // Assign event listeners to all list elements.
    document.querySelectorAll("#left-nav li a").forEach((a) => {
      if (a.hasAttribute("href") && a.href == window.location.href) {
        a.classList.add("active");
      }
    });

    // Temporary code which will be moved to separate codebase after testing.
    this.chatBtn = document.querySelector("#userport-widget-btn");
    this.chatContainer = document.querySelector("#userport-chat-container");
    this.chatBtn.addEventListener(
      "click",
      this.handleChatButtonClick.bind(this)
    );
    this.chatService = new ChatService();
  }

  /**
   * Show or hide dropdown on user click.
   * @param {Event} event
   */
  handleUserAccountClick(event) {
    this.dropDownContent.classList.toggle("show");
  }

  // Temporary code which will be moved to separate codebase after testing.
  handleChatButtonClick() {
    const chatState = this.chatService.toggleState();
    if (chatState === ChatState.OPEN) {
      this.chatBtn.innerText = "X";
    } else {
      this.chatBtn.innerText = "Ask AI";
    }
    this.chatContainer.classList.toggle("userport-hidden");
  }
}
