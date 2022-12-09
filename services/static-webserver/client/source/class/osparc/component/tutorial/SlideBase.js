/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.tutorial.SlideBase", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function(title) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      padding: 5
    });

    if (title) {
      this._add(new qx.ui.basic.Label(title).set({
        font: "title-14"
      }));
    }

    this._populateCard();
  },

  statics: {
    createLabel: function(text) {
      const label = new qx.ui.basic.Label().set({
        rich: true,
        wrap: true,
        font: "text-14"
      });
      if (text) {
        label.setValue(text);
      }
      return label;
    }
  },

  members: {
    /**
      * @abstract
      */
    _populateCard: function() {
      throw new Error("Abstract method called!");
    }
  }
});
