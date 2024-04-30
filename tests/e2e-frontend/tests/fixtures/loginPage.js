export class LoginPage {
  /**
   * @param {import('@playwright/test').Page} page
   * @param {string} productUrl
   */
  constructor(page, productUrl) {
    this.page = page;
    this.productUrl = productUrl;
  }

  async goto() {
    await this.page.goto(this.productUrl);
  }

  /**
   * @param {string} email
   * @param {string} password
   */
  async login(email, password) {
    this.usernameField = this.page.getByTestId("loginUserEmailFld");
    this.passwordField = this.page.getByTestId("loginPasswordFld");
    this.submitButton = this.page.getByTestId("loginSubmitBtn");

    await this.usernameField.fill(email);
    await this.passwordField.fill(password);
    await this.submitButton.click();
  }

  async logout() {
    this.navUserMenuButton = this.page.getByTestId("userMenuBtn");
    await this.navUserMenuButton.click();

    this.navLogoutButton = this.page.getByTestId("userMenuLogoutBtn");
    await this.navLogoutButton.click();
  }
}
