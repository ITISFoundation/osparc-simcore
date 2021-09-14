/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Big button representing a service. It shows its name and icon and description as tooltip.
 * It also adds filtering capabilities.
 */
qx.Class.define("osparc.component.service.ServiceButtonSmall", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function(serviceModel) {
    this.base(arguments);

    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT
    });

    if (serviceModel) {
      this.setServiceModel(serviceModel);
    }

    this.subscribeToFilterGroup("serviceCatalog");
  },

  properties: {
    serviceModel: {
      check: "qx.core.Object",
      nullable: false,
      apply: "__applyServiceModel"
    }
  },

  statics: {
    ITEM_WIDTH: 180,
    ITEM_HEIGHT: 140,
    SERVICE_ICON: "@FontAwesome5Solid/paw/50"
  },

  members: {
    __applyServiceModel: function(serviceModel) {
      serviceModel.bind("name", this.getChildControl("title"), "value");
      if (serviceModel.getThumbnail()) {
        this.setIcon(serviceModel.getThumbnail());
        this.getChildControl("icon").set({
          maxWidth: this.getWidth() - this.getPaddingLeft() - this.getPaddingRight()
        });

        const hint = new osparc.ui.hint.Hint(this, serviceModel.getDescription()).set({
          active: false
        });
        const showHint = () => {
          hint.show();
        };
        const hideHint = () => {
          hint.exclude();
        };
        this.addListener("mouseover", showHint);
        [
          "mouseout",
          "dbltap",
          "keypress"
        ].forEach(e => {
          this.addListener(e, hideHint);
        });
      } else {
        serviceModel.bind("description", this.getChildControl("subtitle-text"), "value");
        this.getChildControl("subtitle-text").set({
          rich: true,
          wrap: true,
          allowGrowY: true
        });
      }
    },

    _filterText: function(text) {
      const checks = [
        this.getServiceModel().getName(),
        this.getServiceModel().getDescription(),
        this.getServiceModel().getContact()
      ];
      return osparc.dashboard.CardBase.filterText(checks, text);
    },

    _filterTags: function(tags) {
      if (tags && tags.length) {
        const type = this.getServiceModel().getType() || "";
        if (!tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    },

    _filterClassifiers: function(classifiers) {
      const checks = this.getServiceModel().getClassifiers();
      return osparc.dashboard.CardBase.filterText(checks, classifiers);
    }
  }
});
