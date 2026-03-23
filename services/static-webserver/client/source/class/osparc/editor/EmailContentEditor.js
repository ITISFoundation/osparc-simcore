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

qx.Class.define("osparc.editor.EmailContentEditor", {
  extend: qx.ui.tabview.TabView,

  construct: function() {
    this.base(arguments);

    this.set({
      contentPadding: 0,
      barPosition: "top"
    });

    this.__quillInstance = null;
    this.__initialContent = "";
    this.__darkModeToggle = null;

    // Initialize HtmlEditor wrapper
    osparc.wrapper.HtmlEditor.getInstance().init()
      .then(() => {
        this.getChildControl("editor-page");
        this.getChildControl("preview-page");
        this.getChildControl("email-editor");
        this.getChildControl("preview-email");
      });

    this.getChildControl("editor-page");
    this.getChildControl("preview-page");
    this.getChildControl("preview-email");

    this.addListener("changeSelection", () => {
      const selectedPage = this.getSelection()[0];
      if (selectedPage.getUserData("id") === "preview-email") {
        this.__composePreview();
      }
      this.__updateTabColors();
    }, this);

    // Set initial tab colors
    this.__updateTabColors();
  },

  properties: {
    templateEmail: {
      check: "String",
      init: "",
      nullable: true,
      apply: "__applyTemplateEmail",
    },

    contentReady: {
      check: "Boolean",
      init: false,
      event: "changeContentReady"
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
          control.setUserData("id", "email-editor");
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
        case "preview-page": {
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

          // Dark mode simulation toolbar
          const toolbar = new qx.ui.container.Composite(new qx.ui.layout.HBox(6).set({
            alignY: "middle"
          })).set({
            padding: [4, 8],
          });
          const darkLabel = new qx.ui.basic.Label(this.tr("Simulate dark mode:")).set({
            alignY: "middle"
          });
          const darkToggle = new qx.ui.form.CheckBox();
          darkToggle.addListener("changeValue", () => {
            if (this.isPreviewActive()) {
              this.__composePreview();
            }
          }, this);
          this.__darkModeToggle = darkToggle;
          toolbar.add(darkLabel);
          toolbar.add(darkToggle);
          control.add(toolbar);

          this.add(control);
          break;
        }
        case "email-editor": {
          const editorId = "email-html-editor-" + Date.now();
          const htmlEditorWrapper = osparc.wrapper.HtmlEditor.getInstance();
          control = htmlEditorWrapper.createEditor(editorId, this.__initialContent, {
            placeholder: 'Write your email...',
            modules: {
              toolbar: osparc.wrapper.HtmlEditor.getRichToolbarConfig()
            }
          });

          // Initialize Quill after the DOM element is ready
          control.addListenerOnce("appear", () => {
            osparc.wrapper.HtmlEditor.makeLayoutFlex(control);

            this.__quillInstance = htmlEditorWrapper.initializeEditor(editorId, control.getUserData("quillOptions"));
            // Set initial content if already loaded
            if (this.__initialContent && this.__quillInstance) {
              this.__setInitialContent();
            }
          }, this);

          this.getChildControl("editor-page").add(control, {
            flex: 1
          });
          break;
        }
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
            minHeight: 300,
          });
          this.getChildControl("preview-page").add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyTemplateEmail: function(templateEmail) {
      if (!templateEmail) {
        return;
      }

      // Extract content section from the template email
      const parser = new DOMParser();
      const doc = parser.parseFromString(templateEmail, "text/html");
      const contentContainer = doc.querySelector(".content");

      if (contentContainer) {
        this.__initialContent = contentContainer.innerHTML;

        // Update Quill editor if already initialized
        if (this.__quillInstance) {
          this.__setInitialContent();
        }
      }
    },

    __setInitialContent: function() {
      const htmlEditorWrapper = osparc.wrapper.HtmlEditor.getInstance();
      htmlEditorWrapper.setHTML(this.__quillInstance, this.__initialContent);

      this.setContentReady(true);
    },

    __composePreview: function() {
      const previewEmail = this.getChildControl("preview-email");

      if (!this.__quillInstance) {
        console.warn("Quill editor not yet initialized");
        return;
      }

      const isDarkMode = this.__darkModeToggle && this.__darkModeToggle.getValue();
      const previewHtml = this.composeWholeHtml(isDarkMode);
      // Use data URL to set HTML content in iframe
      const dataUrl = "data:text/html;charset=utf-8," + encodeURIComponent(previewHtml);
      previewEmail.setSource(dataUrl);
    },

    /**
     * For the current template, compose the whole HTML email by injecting
     * the content from the editor into the template structure.
     *
     * @returns {String} The complete HTML email as a string.
     */
    /**
     * @param {Boolean} [simulateDark=false] - When true, injects CSS that mimics
     *   a dark-mode email client so the preview reflects dark-theme rendering.
     */
    composeWholeHtml: function(simulateDark) {
      const templateHtml = this.getTemplateEmail();
      if (!templateHtml) return "";

      const wrapper = osparc.wrapper.HtmlEditor.getInstance();
      const contentHtml = wrapper.getHTML(this.__quillInstance);
      const parser = new DOMParser();
      const doc = parser.parseFromString(templateHtml, "text/html");

      const contentContainer = doc.querySelector(".content");
      if (contentContainer) {
        contentContainer.innerHTML = contentHtml;
      }

      if (simulateDark) {
        // Telling the document it lives in a dark-mode environment causes the
        // browser to evaluate all @media (prefers-color-scheme: dark) rules
        // inside the iframe naturally — no CSS duplication needed.
        const colorSchemeMeta = doc.createElement("meta");
        colorSchemeMeta.setAttribute("name", "color-scheme");
        colorSchemeMeta.setAttribute("content", "dark");
        doc.head.appendChild(colorSchemeMeta);

        // Simulate the email client's dark canvas — the only thing the email
        // template itself doesn't declare (that's the client app's job).
        const clientDarkStyle = doc.createElement("style");
        clientDarkStyle.textContent = "body { background-color: #1a1a1a !important; }";
        doc.head.appendChild(clientDarkStyle);
      }

      return "<!DOCTYPE html>\n" + doc.documentElement.outerHTML;
    },

    /**
     * Get plain text version of the email body from the editor.
     * @returns {String} The plain text content of the email body.
     */
    getBodyText: function() {
      const wrapper = osparc.wrapper.HtmlEditor.getInstance();
      return wrapper.getText(this.__quillInstance);
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

    isPreviewActive: function() {
      return this.getSelection()[0] === this.getChildControl("preview-page");
    },

    makePreviewActive: function() {
      // make sure quillInstance and content are initialized before switching to preview
      if (this.isContentReady()) {
        this.setSelection([this.getChildControl("preview-page")]);
      } else {
        this.addListenerOnce("changeContentReady", () => {
          this.setSelection([this.getChildControl("preview-page")]);
        }, this);
      }
    },
  }
});
