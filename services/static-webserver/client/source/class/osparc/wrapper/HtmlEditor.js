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

/**
 * @asset(quill/quill-2.0.3.min.js)
 * @asset(quill/quill.snow-2.0.3.css)
 * @ignore(Quill)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://quilljs.com/' target='_blank'>Quill</a>
 */

qx.Class.define("osparc.wrapper.HtmlEditor", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  statics: {
    NAME: "Quill",
    VERSION: "2.0.3",
    URL: "https://quilljs.com/",

    getRichToolbarConfig: function() {
      return [
        [{ 'header': [1, 2, 3, false] }],
        ['bold', 'italic', 'underline', 'strike'],
        ['link', 'blockquote', 'code-block'],
        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
        ['clean']
      ];
    },

    getBasicToolbarConfig: function() {
      return [
        [{ 'header': [1, 2, false] }],
        ['bold', 'italic', 'underline'],
        ['link', 'blockquote', 'code-block'],
        [{ 'list': 'ordered'}, { 'list': 'bullet' }]
      ];
    },
  },

  members: {
    init: function() {
      return new Promise((resolve, reject) => {
        if (this.getLibReady()) {
          resolve();
          return;
        }

        const quillCss = "quill/quill.snow-2.0.3.css";
        const quillCssUri = qx.util.ResourceManager.getInstance().toUri(quillCss);
        qx.module.Css.includeStylesheet(quillCssUri);

        // initialize the script loading
        const quillPath = "quill/quill-2.0.3.min.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          quillPath
        ]);

        dynLoader.addListenerOnce("ready", () => {
          if (typeof Quill === "undefined") {
            reject(new Error("Quill loaded but did not export to window.Quill"));
            return;
          }
          console.log(quillPath + " loaded");
          this.setLibReady(true);

          this.__applyStyles();

          resolve();
        }, this);

        dynLoader.addListener("failed", e => {
          const data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    __applyStyles: function() {
      const styleId = "quill-osparc-style";
      if (!document.getElementById(styleId)) {
        const color = qx.theme.manager.Color.getInstance().resolve("text");
        const style = document.createElement("style");
        style.id = styleId;
        style.innerHTML = `
          .ql-toolbar .ql-stroke {
            stroke: ${color} !important;
          }
          .ql-toolbar .ql-fill {
            fill: ${color} !important;
          }
          .ql-toolbar .ql-picker-label {
            color: ${color} !important;
          }
          .ql-toolbar button:hover .ql-stroke,
          .ql-toolbar button:focus .ql-stroke,
          .ql-toolbar button.ql-active .ql-stroke {
            stroke: ${color} !important;
          }
          .ql-toolbar button:hover .ql-fill,
          .ql-toolbar button:focus .ql-fill,
          .ql-toolbar button.ql-active .ql-fill {
            fill: ${color} !important;
          }
          .ql-editor.ql-blank::before {
            color: ${color} !important;
            opacity: 0.6;
          }
        `;
        document.head.appendChild(style);
      }
    },

    createEditor: function(divId, initialContent = "", options = {}) {
      // Create container with initial content if provided
      const htmlContent = initialContent || "<p><br /></p>";
      const container = new qx.ui.embed.Html("<div id='"+divId+"'>"+htmlContent+"</div>");
      container.setUserData("quillDivId", divId);

      // Default options following Quill documentation
      const defaultOptions = {
        theme: 'snow',
        placeholder: 'Start typing...',
        modules: {
          toolbar: [
            [{ 'header': [1, 2, false] }],
            ['bold', 'italic', 'underline'],
            ['link', 'blockquote', 'code-block'],
            [{ 'list': 'ordered'}, { 'list': 'bullet' }]
          ]
        }
      };

      // Store options for later initialization
      container.setUserData("quillOptions", { ...defaultOptions, ...options });

      return container;
    },

    initializeEditor: function(divId, options = null) {
      const element = document.getElementById(divId);
      if (!element) {
        console.error(`Element with id ${divId} not found`);
        return null;
      }

      // If options not provided, try to get from container userData
      if (!options) {
        const container = element.parentElement;
        if (container && container.__userData) {
          options = container.__userData.quillOptions;
        }
      }

      // Initialize Quill with the standard pattern: new Quill('#selector', options)
      const quill = new Quill(`#${divId}`, options || { theme: 'snow' });
      return quill;
    },

    getHTML: function(quill) {
      return quill.root.innerHTML;
    },

    setHTML: function(quill, html) {
      return;
      const delta = quill.clipboard.convert(html);
      quill.setContents(delta, 'silent');
    },

    getText: function(quill) {
      return quill.getText();
    },
  }
});
