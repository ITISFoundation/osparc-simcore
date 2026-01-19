/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.EmailEditor", {
  extend: qx.ui.tabview.TabView,

  construct: function() {
    this.base(arguments);

    this.set({
      contentPadding: 0,
      barPosition: "top"
    });

    this.getChildControl("editor-page");
    this.getChildControl("preview-page");
    this.getChildControl("text-editor");
    this.getChildControl("preview-email");

    this.addListener("changeSelection", () => {
      const selectedPage = this.getSelection()[0];
      if (selectedPage.getUserData("id") === "preview-email") {
        this.__renderPreview();
      }
      this.__updateTabColors();
    }, this);

    // Set initial tab colors
    this.__updateTabColors();

    osparc.store.Faker.getInstance().fetchEmailTemplate("free-email")
      .then(templateEmail => {
        this.setTemplateEmail(templateEmail.body);
      });
  },

  properties: {
    templateEmail: {
      check: "String",
      init: "",
      nullable: true,
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "editor-page":
          control = new qx.ui.tabview.Page(this.tr("Editor")).set({
            layout: new qx.ui.layout.VBox()
          });
          control.setUserData("id", "text-editor");
          // Style the tab button for better active state visibility
          control.getButton().set({
            padding: [4, 8],
          });
          // Remove rounded bottom edges
          control.getButton().addListenerOnce("appear", () => {
            control.getButton().getContentElement().setStyles({
              "border-bottom-left-radius": "0px",
              "border-bottom-right-radius": "0px"
            });
          });
          this.add(control);
          break;
        case "preview-page":
          control = new qx.ui.tabview.Page(this.tr("Preview")).set({
            layout: new qx.ui.layout.VBox()
          });
          control.setUserData("id", "preview-email");
          // Style the tab button for better active state visibility
          control.getButton().set({
            padding: [4, 8],
          });
          // Remove rounded bottom edges
          control.getButton().addListenerOnce("appear", () => {
            control.getButton().getContentElement().setStyles({
              "border-bottom-left-radius": "0px",
              "border-bottom-right-radius": "0px"
            });
          });
          this.add(control);
          break;
        case "text-editor":
          control = new osparc.editor.MarkdownEditorInline().set({
            allowGrowY: true,
            allowGrowX: true,
            minWidth: 500,
            minHeight: 500,
          });
          control.getChildControl("text-area").set({
            placeholder: "Write your email..."
          });
          this.getChildControl("editor-page").add(control, {
            flex: 1
          });
          break;
        case "preview-email":
          // using qx.ui.embed.Iframe instead of qx.ui.embed.Html because:
          // - CSS isolation
          // - The template is a full HTML document
          // - Security: avoids script execution
          // - Much closer to real email rendering
          control = new qx.ui.embed.Iframe().set({
            allowGrowY: true,
            allowGrowX: true,
            minWidth: 500,
            minHeight: 500,
          });
          this.getChildControl("preview-page").add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __renderPreview: function() {
      const previewEmail = this.getChildControl("preview-email");

      const textEditor = this.getChildControl("text-editor");
      const emailContentText = textEditor.getValueAsHtml();
      // Convert the line breaks
      const emailContentHtml = emailContentText.replaceAll("\n", "<br/>");
      const templateEmail = this.getTemplateEmail();
      const previewHtml = this.__buildPreviewHtml(templateEmail, emailContentHtml);

      // Use data URL to set HTML content in iframe
      const dataUrl = "data:text/html;charset=utf-8," + encodeURIComponent(previewHtml);
      previewEmail.setSource(dataUrl);
    },

    __buildPreviewHtml(templateHtml, contentHtml) {
      if (!templateHtml) return "";

      const parser = new DOMParser();
      const doc = parser.parseFromString(templateHtml, "text/html");

      const contentContainer = doc.querySelector(".content");
      if (contentContainer) {
        contentContainer.innerHTML = contentHtml;
      }

      return "<!DOCTYPE html>\n" + doc.documentElement.outerHTML;
    },

    __updateTabColors: function() {
      const selectedPage = this.getSelection()[0];
      [this.getChildControl("editor-page"), this.getChildControl("preview-page")].forEach(page => {
        const isActive = page === selectedPage;
        page.getButton().set({
          backgroundColor: isActive ? "fab-background" : "background-main-2",
        });
      });
    },
  }
});
