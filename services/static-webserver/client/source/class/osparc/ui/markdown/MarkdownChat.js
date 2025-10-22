/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2025 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * @asset(marked/marked.min.js)
 * @asset(marked/markdown.css)
 * @ignore(marked)
 */

/* global marked */

qx.Class.define("osparc.ui.markdown.MarkdownChat", {
  extend: qx.ui.embed.Html,

  /**
   * @param {String} markdown Plain text accepting markdown syntax
   */
  construct: function(markdown) {
    this.base(arguments);

    this.set({
      allowGrowX: false,
      allowGrowY: true,
      overflowX: "hidden", // hide scrollbars
      overflowY: "hidden", // hide scrollbars
    });

    const markdownCssUri = qx.util.ResourceManager.getInstance().toUri("marked/markdown.css");
    qx.module.Css.includeStylesheet(markdownCssUri);

    this.__loadMarked = new Promise((resolve, reject) => {
      if (typeof marked === "function") {
        resolve(marked);
      } else {
        const loader = new qx.util.DynamicScriptLoader([
          "marked/marked.min.js"
        ]);
        loader.addListenerOnce("ready", () => resolve(marked), this);
        loader.addListenerOnce("failed", e =>
          reject(Error(`Failed to load ${e.getData()}`))
        );
        loader.start();
      }
    });

    if (markdown) {
      this.setValue(markdown);
    }

    this.addListenerOnce("appear", () => {
      this.getContentElement().addClass("osparc-markdown");
      this.__scheduleResize(); // first paint sizing
    });
  },

  properties: {
    /**
     * Holds the raw markdown text and updates the label's {@link #value} whenever new markdown arrives.
     */
    value: {
      check: "String",
      apply: "__applyMarkdown"
    },

    measurerMaxWidth: {
      check: "Integer",
      init: 220,
      nullable: true,
    },
  },

  events: {
    "resized": "qx.event.type.Event",
  },

  statics: {
    MD_ROOT: "osparc-md-root",
    MD_MEASURE: "osparc-md-measure",
  },

  members: {
    __loadMarked: null,

    /**
     * Apply function for the markdown property. Compiles the markdown text to HTML and applies it to the value property of the label.
     * @param {String} value Plain text accepting markdown syntax.
     */
    __applyMarkdown: function(value = "") {
      this.__loadMarked.then(() => {
        const renderer = {
          link(link) {
            const linkColor = qx.theme.manager.Color.getInstance().resolve("link");
            let linkHtml = `<a href="${link.href}" title="${link.title || ""}" style="color: ${linkColor};">`
            if (link.tokens && link.tokens.length) {
              const linkRepresentation = link.tokens[0];
              if (linkRepresentation.type === "text") {
                linkHtml += linkRepresentation.text;
              } else if (linkRepresentation.type === "image") {
                linkHtml += `<img src="${linkRepresentation.href}" title alt="${linkRepresentation.text}"></img>`;
              }
            }
            linkHtml += `</a>`;
            return linkHtml;
          }
        };
        marked.use({ renderer });
        // By default, Markdown requires two spaces at the end of a line or a blank line between paragraphs to produce a line break.
        // With this, a single line break (Enter) in your Markdown input will render as a <br> in HTML.
        marked.setOptions({ breaks: true });

        const html = marked.parse(value);

        const safeHtml = osparc.wrapper.DOMPurify.sanitize(html);

        // flow-root prevents margin collapsing; inline style avoids extra stylesheet juggling
        const max = this.getMeasurerMaxWidth() || 220;
        const mdRoot = `
          <div class="${this.self().MD_ROOT}" style="display:flow-root;">
            <div class="${this.self().MD_MEASURE}"
                style="
                  display:inline-block;
                  width:max-content;
                  max-width:${max}px;
                  white-space:normal;
                  overflow-wrap:anywhere; /* break long tokens */
                ">
              ${safeHtml}
            </div>
          </div>
        `;
        this.setHtml(mdRoot);

        // resize once DOM is updated/painted
        this.__scheduleResize();

        // also resize once images load (they change height later)
        const el = this.__getDomElement();
        if (el) {
          el.querySelectorAll("img").forEach(img => {
            if (!img.complete) {
              img.addEventListener("load", () => this.__scheduleResize(), { once: true });
              img.addEventListener("error", () => this.__scheduleResize(), { once: true });
            }
          });
        }

        // safety net; sometimes we miss an image load or so
        setTimeout(() => this.__scheduleResize(), 500);
      }).catch(error => console.error(error));
    },

    __getDomElement: function() {
      if (!this.getContentElement || this.getContentElement() === null) {
        return null;
      }
      const domElement = this.getContentElement().getDomElement();
      if (domElement) {
        return domElement;
      }
      return null;
    },

    __scheduleResize: function() {
      const dom = this.__getDomElement();
      if (!dom) {
        return;
      }

      // collapse first so we don't re-measure an old minHeight
      this.setHeight(null);
      this.setMinHeight(0);
      this.setWidth(null);
      this.setMinWidth(0);

      window.requestAnimationFrame(() => {
        // force reflow
        void dom.offsetHeight;

        // measure the wrapper we injected (covers ALL children)
        const root = dom.querySelector("."+this.self().MD_ROOT) || dom;
        const meas = root.querySelector("."+this.self().MD_MEASURE) || root;

        const rect = meas.getBoundingClientRect();
        const rH = Math.ceil(rect.height || 0);
        const rW = Math.ceil(rect.width || 0);

        // include widget insets (decorator/padding/border)
        const insets = this.getInsets ? this.getInsets() : { top:0, right:0, bottom:0, left:0 };
        const totalH = Math.ceil((rH || 0) + (insets.top || 0) + (insets.bottom || 0));
        const totalW = Math.ceil((rW || 0) + (insets.left || 0) + (insets.right || 0));

        this.setMinHeight(totalH);
        this.setHeight(totalH);

        // width: shrink-to-fit, but cap at a max
        this.setMaxWidth(null); // measurer already capped; we set exact width
        this.setMinWidth(1); // avoid 0 when empty
        this.setWidth(totalW);

        this.fireEvent("resized");
      });
    },
  }
});
