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
    }, this);

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
          control = new qx.ui.tabview.Page(this.tr("Editor"));
          control.setUserData("id", "text-editor");
          this.add(control);
          break;
        case "preview-page":
          control = new qx.ui.tabview.Page(this.tr("Preview"));
          control.setUserData("id", "preview-email");
          this.add(control);
          break;
        case "text-editor":
          control = new qx.ui.form.TextArea().set({
            placeholder: "Write your email..."
          });
          this.getChildControl("editor-page").add(control);
          break;
        case "preview-email":
          // using qx.ui.embed.Iframe instead of qx.ui.embed.Html because:
          // - CSS isolation
          // - The template is a full HTML document
          // - Security: avoids script execution
          // - Much closer to real email rendering
          control = new qx.ui.embed.Iframe();
          this.getChildControl("preview-page").add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __renderPreview: function() {
      const previewEmail = this.getChildControl("preview-email");
      previewEmail.setHtml("<b>Rendering preview...</b>");

      const textEditor = this.getChildControl("text-editor");
      const emailContent = textEditor.getValue();
      const templateEmail = this.getTemplateEmail();

      const previewHtml = this.__buildPreviewHtml(templateEmail, emailContent);
      previewEmail.setHtml(previewHtml);
    },

    __escapeHtml: function(str) {
      return (str || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    },

    __draftTextToHtml(text) {
      // simple + safe: plain text -> <br>
      const safe = this.__escapeHtml((text || "").trim());
      return safe.replaceAll("\n", "<br/>");
    },

    __buildPreviewHtml(templateHtml, contentHtml) {
      if (!templateHtml) return "";

      const parser = new DOMParser();
      const doc = parser.parseFromString(templateHtml, "text/html");

      // Prefer a stable marker if you can add it later:
      // const mount = doc.querySelector("[data-email-content]") || doc.querySelector(".content");
      const mount = doc.querySelector(".content");
      if (mount) {
        mount.innerHTML = contentHtml;
      }

      console.log("Preview HTML:", doc.documentElement.outerHTML);

      return "<!DOCTYPE html>\n" + doc.documentElement.outerHTML;
    },
  }
});
