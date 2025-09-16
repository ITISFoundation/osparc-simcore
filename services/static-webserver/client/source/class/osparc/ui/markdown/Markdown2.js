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

/**
 * This class is just a special kind of rich label that takes markdown raw text, compiles it to HTML,
 * sanitizes it and applies it to its value property.
 */
qx.Class.define("osparc.ui.markdown.Markdown2", {
  extend: qx.ui.embed.Html,

  /**
   * Markdown constructor. It directly accepts markdown as its first argument.
   * @param {String} markdown Plain text accepting markdown syntax. Its compiled version will be set in the value property of the label.
   */
  construct: function(markdown) {
    this.base(arguments);

    this.set({
      allowGrowX: true,
      allowGrowY: true,
      overflowX: "hidden",
      overflowY: "hidden",
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
  },

  events: {
    "resized": "qx.event.type.Event",
  },

  statics: {
    WRAP_CLASS: "osparc-md-root"
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
                linkHtml += `<img src="${linkRepresentation.href}" tile alt="${linkRepresentation.text}"></img>`;
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

        const safeHtml = osparc.wrapper.DOMPurify.getInstance().sanitize(html);

        // flow-root prevents margin collapsing; inline style avoids extra stylesheet juggling
        let mdRoot;
        const max = 220;
        if (max) {
          mdRoot = `
            <div class="${this.self().WRAP_CLASS}" style="display:flow-root;">
              <div class="osparc-md-measure"
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
        } else {
          mdRoot = `
            <div class="${this.self().WRAP_CLASS}" style="display:flow-root;">
              ${safeHtml}
            </div>`;
        }
        this.setHtml(mdRoot);

        // resize once DOM is updated/painted
        this.__scheduleResize();

        // also resize once images load (they change height later)
        const el = this.__getDomElement();
        if (el) {
          el.querySelectorAll("img").forEach(img => {
            if (!img.complete) {
              img.addEventListener("load", () => this.__scheduleResize(), { once: true });
            }
          });
        }
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
      const domElement = this.__getDomElement();
      if (!domElement) {
        return;
      }

      // collapse first so we don't re-measure an old minHeight
      this.setHeight(null);
      this.setMinHeight(0);
      this.setWidth(null);
      this.setMinWidth(0);

      window.requestAnimationFrame(() => {
        // force reflow
        void domElement.offsetHeight;

        // measure the wrapper we injected (covers ALL children)
        const root = domElement.querySelector("."+this.self().WRAP_CLASS) || domElement;
        const meas = root.querySelector(".osparc-md-measure") || root;

        const rH = meas.getBoundingClientRect().height;
        const rW = meas.getBoundingClientRect().width;

        // include widget insets (decorator/padding/border)
        const insets = this.getInsets ? this.getInsets() : { top:0, right:0, bottom:0, left:0 };
        const totalH = Math.ceil((rH || 0) + (insets.top || 0) + (insets.bottom || 0));
        const totalW = Math.ceil((rW || 0) + (insets.left || 0) + (insets.right || 0));

        this.setMinHeight(totalH);
        this.setHeight(totalH);

        // width: shrink-to-fit, but cap at a max
        this.setAllowGrowX(false);     // prevent parent layout from stretching it
        this.setMaxWidth(null);        // measurer already capped; we set exact width
        this.setMinWidth(1);           // avoid 0 when empty
        this.setWidth(totalW);         // exact bubble width

        console.log("totalH", totalH, "totalW", totalW);
      });
    },
  }
});
