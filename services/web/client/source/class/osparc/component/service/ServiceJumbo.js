/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Big button representing a service. It shows it name, description and contact information. It also adds
 * filtering capabilities.
 */
qx.Class.define("osparc.component.service.ServiceJumbo", {
  extend: osparc.ui.form.Jumbo,
  include: osparc.component.filter.MFilterable,
  implement: osparc.component.filter.IFilterable,

  /**
   * Constructor
   */
  construct: function(serviceModel, icon) {
    const label = serviceModel.getName ? serviceModel.getName() : "";
    const text = serviceModel.getDescription ? serviceModel.getDescription() : "";
    const footer = serviceModel.getContact ? serviceModel.getContact() : "";
    this.base(arguments, label, text, icon, footer);
    if (serviceModel != null) { // eslint-disable-line no-eq-null
      this.setServiceModel(serviceModel);
    }
  },

  properties: {
    serviceModel: {
      check: "qx.core.Object",
      nullable: false
    }
  },

  members: {
    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const label = this.getServiceModel().getName()
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const category = this.getServiceModel().getCategory() || "";
        const type = this.getServiceModel().getType() || "";
        if (!data.tags.includes(osparc.utils.Utils.capitalize(category.trim())) && !data.tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      return false;
    }
  }
});
