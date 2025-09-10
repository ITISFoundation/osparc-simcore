/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.widget.JsonFormatterWidget", {
  extend: qx.ui.core.Widget,

  construct: function(json) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Grow());
    if (json) {
      this.setJson(json);
    }
  },

  members: {
    __formatterEl: null,
    __root: null,

    _createContentElement: function() {
      this.__root = new qx.html.Element("div");
      this.__root.addClass("osparc-json-formatter-root");
      this.__root.setStyles({
        width: "100%",
        height: "100%",
        boxSizing: "border-box"
      });
      return this.__root;
    },

    setJson: function(json) {
      if (!this.getContentElement().getDomElement()) {
        this.addListenerOnce("appear", () => this._mountJson(json), this);
      } else {
        this._mountJson(json);
      }

      this.__applyStyles();
    },

    _mountJson: function(json) {
      if (this.__formatterEl && this.__formatterEl.parentNode) {
        this.__formatterEl.parentNode.removeChild(this.__formatterEl);
        this.__formatterEl = null;
      }

      let jsonObj = json;
      if (typeof json === "string") {
        try {
          jsonObj = JSON.parse(json);
        } catch (e) {
          console.warn("setJson(): invalid JSON string, rendering raw", e);
        }
      }

      if (typeof JSONFormatter === "undefined") {
        console.error("JSONFormatter is not available");
        return;
      }

      // Hardcoded options
      const formatter = new JSONFormatter(jsonObj, 2, {

      });
      this.__formatterEl = formatter.render();

      // Apply styling
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      this.__formatterEl.style.setProperty("color", color, "important");
      this.__formatterEl.style.setProperty("font-family", '"Manrope", sans-serif', "important");

      // Keys font-size
      this.__formatterEl.querySelectorAll(".json-formatter-key").forEach(el => {
        el.style.setProperty("font-size", "13px", "important");
      });

      // Hide constructor names
      this.__formatterEl.querySelectorAll(".json-formatter-constructor-name").forEach(el => {
        el.style.setProperty("display", "none", "important");
      });

      const rootDom = this.getContentElement().getDomElement();
      if (rootDom) {
        rootDom.appendChild(this.__formatterEl);
      }
    },
  },

  destruct: function() {
    if (this.__formatterEl && this.__formatterEl.parentNode) {
      this.__formatterEl.parentNode.removeChild(this.__formatterEl);
    }
  }
});
