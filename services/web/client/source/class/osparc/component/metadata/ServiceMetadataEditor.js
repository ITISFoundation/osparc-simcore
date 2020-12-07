/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.metadata.ServiceMetadataEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Grow());

    this.__serviceData = serviceData;

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView(serviceData);
    this.__stack.add(this.__displayView);
    this._add(this.__stack);
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "display",
      nullable: false,
      apply: "_applyMode"
    }
  },

  statics: {
    getDummyMetadataTSR: function() {
      const dummyMetadataTSR = {
        "tsrScore": Math.floor(Math.random()*(40))
      };
      return dummyMetadataTSR;
    }
  },

  members: {
    __serviceData: null,
    __stack: null,
    __displayView: null,
    __editView: null,

    __createDisplayView: function(serviceData) {
      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      console.log(serviceData);
      return displayView;
    },

    _applyMode: function(mode) {
      switch (mode) {
        case "display":
          this.__stack.setSelection([this.__displayView]);
          break;
      }
    },

    __isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (myGid && osparc.component.export.ServicePermissions.canGroupWrite(this.__serviceData["access_rights"], myGid)) {
        return true;
      }
      return false;
    }
  }
});
