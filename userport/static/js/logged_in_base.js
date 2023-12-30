export class LoggedInBaseView {
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
  }

  /**
   * Show or hide dropdown on user click.
   * @param {Event} event
   */
  handleUserAccountClick(event) {
    this.dropDownContent.classList.toggle("show");
  }
}
