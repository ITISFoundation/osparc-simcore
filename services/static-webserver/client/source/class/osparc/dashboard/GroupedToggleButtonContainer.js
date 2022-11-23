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

qx.Class.define("osparc.dashboard.GroupedToggleButtonContainer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__buildLayout();
  },

  properties: {
    groupHeader: {
      check: qx.ui.core.Widget,
      init: null,
      nullable: true,
      apply: "__applyGroupHeader"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "container":
          control = new osparc.component.widget.SlideBar().set({
            alignX: "center",
            maxHeight: 170
          });
          control.setButtonsWidth(30);
          this._addAt(control, 1);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyGroupHeader: function(header) {
      this._addAt(header, 0);
    }
  }
});
