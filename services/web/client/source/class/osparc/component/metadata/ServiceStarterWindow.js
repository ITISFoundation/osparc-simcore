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


qx.Class.define("osparc.component.metadata.ServiceStarterWindow", {
  extend: osparc.component.metadata.ServiceInfoWindow,

  /**
    * @param metadata {Object} Service metadata
    */
  construct: function(metadata) {
    this.base(arguments, metadata);

    this.__service = metadata;

    const toolboxContainer = this.__createToolbox();
    this.addAt(toolboxContainer, 0);
  },

  members: {
    __serviceKey: null,
    __versionsUIBox: null,

    __createToolbox: function() {
      const toolboxContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      const versionsList = this.__createVersionsList();
      toolboxContainer.add(versionsList);

      toolboxContainer.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const openButton = new qx.ui.form.Button(this.tr("Open")).set({
        appearance: "md-button"
      });
      toolboxContainer.add(openButton);

      return toolboxContainer;
    },

    __createVersionsList: function() {
      const versionsList = this.__versionsUIBox = new qx.ui.form.SelectBox().set({
        font: "text-14"
      });
      // populate versions
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const versions = osparc.utils.Services.getVersions(services, this.__service.key);
          if (versions) {
            let lastItem = null;
            versions.forEach(version => {
              lastItem = new qx.ui.form.ListItem(version).set({
                font: "text-14"
              });
              versionsList.add(lastItem);
            });
            if (lastItem) {
              versionsList.setSelection([lastItem]);
              this.__versionSelected(lastItem.getLabel());
            }
          }
        });
      versionsList.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length) {
          this.__versionSelected(e.getData()[0].getLabel());
        }
      }, this);

      return versionsList;
    },

    __versionSelected: function(serviceVersion) {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const selectedService = osparc.utils.Services.getFromObject(services, this.__service.key, serviceVersion);
          this._serviceInfo.setService(selectedService);
        });
    }
  }
});
