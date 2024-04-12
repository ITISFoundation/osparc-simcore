/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.ResourceDetailsWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function(resourceData) {
    const resourceAlias = osparc.utils.Utils.resourceTypeToAlias(resourceData["resourceType"]);
    const title = `${resourceAlias} ${qx.locale.Manager.tr("Details")} - ${resourceData.name}`;
    this.base(arguments, "resource-details", title);

    const width = 830;
    const height = 700;
    this.set({
      width: width,
      height: height,
    });

    const resourceDetails = this.__resourceDetails = new osparc.dashboard.ResourceDetails(resourceData);
    this._setTabbedView(resourceDetails);
  },

  statics: {
    openWindow: function(resourceData) {
      const resourceDetailsWindow = new osparc.dashboard.ResourceDetailsWindow(resourceData);
      resourceDetailsWindow.center();
      resourceDetailsWindow.open();
      return resourceDetailsWindow;
    }
  },

  members: {
    __resourceDetails: null,

    getResourceDetails: function() {
      return this.__resourceDetails;
    }
  },

  destruct: function() {
    this.remove(this.__resourceDetails);
    this.__resourceDetails = null;
  }
});
