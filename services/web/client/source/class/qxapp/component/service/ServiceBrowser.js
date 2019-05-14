/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * View to browse services.
 */
qx.Class.define("qxapp.component.service.ServiceBrowser", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor
   */
  construct: function(filterId, groupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Flow(5, 5));
  },

  properties: {
    appearance: {
      refine: true,
      init: "service-browser"
    },
    model: {
      nullable: true,
      check: "qx.data.Array",
      apply: "_applyModel"
    }
  },

  members: {
    buttons: null,
    _applyModel: function(model) {
      this._removeAll();
      model.toArray().forEach((service, index) => {
        const button = new qxapp.component.service.ServiceJumbo(service, "@FontAwesome5Solid/info-circle/16");
        button.subscribeToFilterGroup("service-catalogue");
        this.__buttons = [];
        this.__buttons.push(button);
        this._add(button);
      });
    }
  }
});
