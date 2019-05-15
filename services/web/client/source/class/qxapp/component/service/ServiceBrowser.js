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

  events: {
    "changeValue": "qx.event.type.Data",
    "servicedbltap": "qx.event.type.Data"
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
    __buttonGroup: null,

    _applyModel: function(model) {
      this._removeAll();
      const group = this.__buttonGroup = new qx.ui.form.RadioGroup().set({
        allowEmptySelection: true
      });
      model.toArray().forEach(service => {
        const button = new qxapp.component.service.ServiceJumbo(service, "@FontAwesome5Solid/info-circle/16");
        button.subscribeToFilterGroup("service-catalogue");
        group.add(button);
        this._add(button);
        button.addListener("dbltap", e => {
          this.fireDataEvent("servicedbltap", button.getServiceModel());
        }, this);
      });
      group.addListener("changeValue", e => this.dispatchEvent(e.clone()), this);
    },

    getSelected: function() {
      if (this.__buttonGroup && this.__buttonGroup.getSelection().length) {
        return this.__buttonGroup.getSelection()[0].getServiceModel();
      }
      return null;
    },

    isSelectionEmpty: function() {
      if (this.__buttonGroup == null) { // eslint-disable-line no-eq-null
        return true;
      }
      return this.__buttonGroup.getSelection().length === 0;
    },

    selectFirstVisible: function() {
      if (this._hasChildren()) {
        const buttons = this._getChildren();
        let current = buttons[0];
        let i = 1;
        while (i<buttons.length && !current.isVisible()) {
          current = buttons[i++];
        }
        if (current.isVisible()) {
          this.__buttonGroup.setSelection([this._getChildren()[i-1]]);
        }
      }
    }
  }
});
