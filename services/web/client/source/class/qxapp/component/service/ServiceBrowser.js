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
 * This is a view to display the available services in a flowing fashion. Creates a ServiceJumbo button
 * for every service in the model and subscribes it to the filter group.
 */
qx.Class.define("qxapp.component.service.ServiceBrowser", {
  extend: qx.ui.core.Widget,

  /**
   * If the optional parameter is given, the elements will be subscribed to the filter group of the given id.
   *
   * @param {String} [groupId] Id of the filter group the service Jumbo buttons will be subscribed to.
   */
  construct: function(groupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Flow(5, 5));
    if (groupId) {
      this.__filterGroup = groupId;
    }
  },

  events: {
    "changeValue": "qx.event.type.Data",
    "serviceadd": "qx.event.type.Data"
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
    __filterGroup: null,

    _applyModel: function(model) {
      this._removeAll();
      const group = this.__buttonGroup = new qx.ui.form.RadioGroup().set({
        allowEmptySelection: true
      });
      model.toArray()
        .sort((a, b) => a.getName().localeCompare(b.getName()))
        .forEach(service => {
          const button = new qxapp.component.service.ServiceJumbo(service);
          if (this.__filterGroup !== null) {
            button.subscribeToFilterGroup(this.__filterGroup);
          }
          group.add(button);
          this._add(button);
          button.addListener("dbltap", e => {
            this.fireDataEvent("serviceadd", button.getServiceModel());
          }, this);
          button.addListener("keypress", e => {
            if (e.getKeyIdentifier() === "Enter") {
              this.fireDataEvent("serviceadd", button.getServiceModel());
            }
          }, this);
        });
      group.addListener("changeValue", e => this.dispatchEvent(e.clone()), this);
    },

    /**
     * Public function to get the currently selected service.
     *
     * @return Returns the model of the selected service or null if selection is empty.
     */
    getSelected: function() {
      if (this.__buttonGroup && this.__buttonGroup.getSelection().length) {
        return this.__buttonGroup.getSelection()[0].getServiceModel();
      }
      return null;
    },

    /**
     * Function checking if the selection is empty or not
     *
     * @return True if no item is selected, false if there one or more item selected.
     */
    isSelectionEmpty: function() {
      if (this.__buttonGroup == null) { // eslint-disable-line no-eq-null
        return true;
      }
      return this.__buttonGroup.getSelection().length === 0;
    },

    /**
     * Function that selects the first visible button.
     */
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
