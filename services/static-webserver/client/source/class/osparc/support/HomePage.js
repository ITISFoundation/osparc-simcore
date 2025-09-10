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


qx.Class.define("osparc.support.HomePage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.getChildControl("conversations-intro-text");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversations-intro-text": {
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-14",
          });
          const isSupportUser = osparc.store.Groups.getInstance().amIASupportUser();
          control.set({
            value: isSupportUser ?
              this.tr("Hello Support User!") :
              this.tr("Hello User!"),
          });
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },
  }
});
