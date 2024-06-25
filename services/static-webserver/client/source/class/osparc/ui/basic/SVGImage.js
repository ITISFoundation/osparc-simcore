/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that displays an svg image and support changing its color.
 * It is meant to be used for those images that are not available in the catalog of font icons we include.
 */


qx.Class.define("osparc.ui.basic.SVGImage", {
  extend: qx.ui.core.Widget,

  /**
   * @param source
   */
  construct: function(source) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      alignX: "center",
      alignY: "middle"
    });

    if (source) {
      this.setSource(source);
    }
  },

  properties: {
    source: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__applySource"
    },

    imageColor: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeImageColor",
      apply: "__applyImageColor"
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "image":
          control = new qx.ui.basic.Image().set({
            scale: true,
            alignX: "center",
            alignY: "middle"
          });
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applySource: function(src) {
      if (src && src.includes(".svg")) {
        this.getChildControl("image").setSource(src);
      }
    },

    __applyImageColor: function() {
      const myStyle = {
        "filter": "invert(48%) sepia(79%) saturate(2476%) hue-rotate(86deg) brightness(118%) contrast(119%)"
      };
      this.getChildControl("image").getContentElement().setStyles(myStyle);
    },

    setSize: function(size) {
      this.getChildControl("image").set({
        height: size.height,
        width: size.width
      });
    }
  }
});
