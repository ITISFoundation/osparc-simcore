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

    const pandiSize = 100;
    const pandi = new qx.ui.basic.Image("osparc/panda.gif").set({
      width: pandiSize,
      height: pandiSize,
      scale: true
    });

    this._add(pandi, {
      bottom: 0,
      right: 0
    });
  }
});
