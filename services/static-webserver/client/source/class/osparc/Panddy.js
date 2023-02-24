/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.Panddy", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());
    this.getChildControl("panddy");

    setTimeout(() => {
      this.getChildControl("bubble-text").setValue(osparc.Panddy.INTRO_TEXT);
    }, 2000);
  },

  statics: {
    INTRO_TEXT: qx.locale.Manager.tr("Hey there!<br>This is Panddy. I'm here to give you hints on how to use oSPARC.")
  },

  members: {
    _createChildControlImpl: function(id) {
      const pandiSize = 100;
      let control;
      switch (id) {
        case "panddy": {
          control = new qx.ui.basic.Image("osparc/panda.gif").set({
            width: pandiSize,
            height: pandiSize,
            scale: true,
            cursor: "pointer"
          });
          this._add(control, {
            bottom: 0,
            right: 0
          });
          break;
        }
        case "bubble-text":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            backgroundColor: "c05",
            padding: 10,
            rich: true,
            maxWidth: 300
          });
          control.getContentElement().setStyles({
            "border-radius": "8px"
          });
          this._add(control, {
            bottom: pandiSize-20,
            right: pandiSize-20
          });
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});
