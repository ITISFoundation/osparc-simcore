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

    this.set({
      allowGrowX: true,
      allowGrowY: true,
      width: null,
      height: null
    });

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
        boxSizing: "border-box",
        overflow: "auto" // ensure local overflow is visible
      });
      return this.__root;
    },

    _getContentHint: function() {
      if (this.__formatterEl) {
        return {
          width: this.__formatterEl.scrollWidth,
          height: this.__formatterEl.scrollHeight
        };
      }
      return { width: 100, height: 50 };
    },

    setJson: function(json) {
      if (!this.getContentElement().getDomElement()) {
        this.addListenerOnce("appear", () => this._mountJson(json), this);
      } else {
        this._mountJson(json);
      }
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

      const formatter = new JSONFormatter(jsonObj, 2, {});
      this.__formatterEl = formatter.render();

      const rootDom = this.getContentElement().getDomElement();
      if (rootDom) {
        rootDom.appendChild(this.__formatterEl);
      }
      this.invalidateLayoutCache(); // notify qooxdoo to recalc size
    },
  },

  destruct: function() {
    if (this.__formatterEl && this.__formatterEl.parentNode) {
      this.__formatterEl.parentNode.removeChild(this.__formatterEl);
    }
  }
});
