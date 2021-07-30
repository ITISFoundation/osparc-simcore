/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.component.service.ServiceButtonSmall", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function(serviceModel) {
    this.base(arguments);

    this.set({
      width: 180,
      height: 150
    });

    if (serviceModel) {
      this.setServiceModel(serviceModel);
    }
  },

  properties: {
    serviceModel: {
      check: "qx.core.Object",
      nullable: false,
      apply: "__applyResourceData"
    }
  },

  statics: {
    SERVICE_ICON: "@FontAwesome5Solid/paw/50"
  },

  members: {

    __applyResourceData: function(serviceModel) {
      serviceModel.bind("name", this.getChildControl("title"), "value");
      serviceModel.bind("thumbnail", this.getChildControl("icon").getChildControl("image"), "source", {
        converter: value => value === null ? this.self().SERVICE_ICON : value
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
      this.addListener("mouseout", hideHint);
    },

    __filterText: function(text) {
      if (text) {
        const checks = [
          this.getServiceModel().getName()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(text)).length == 0) {
          return true;
        }
      }
      return false;
    },

    __filterTags: function(tags) {
      if (tags && tags.length) {
        const type = this.getServiceModel().getType() || "";
        if (!tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    },

    _shouldApplyFilter: function(data) {
      if (this.__filterText(data.text)) {
        return true;
      }
      if (this.__filterTags(data.tags)) {
        return true;
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
