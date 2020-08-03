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


qx.Class.define("osparc.component.metadata.ServiceVersionDetails", {
  extend: osparc.component.metadata.ServiceDetails,

  /**
    * @param serviceData {Object} Service metadata
    */
  construct: function(serviceData) {
    this.base(arguments, serviceData);

    this.__createVersionSelector();

    this.addListener("changeService", e => {
      const newServ = e.getData();
      const oldServ = e.getOldData();
      if (oldServ && oldServ.key === newServ.key) {
        return;
      }
      this.__createVersionSelector();
    }, this);
  },

  members: {
    __versionSelector: null,

    __createVersionSelector: function() {
      const versionSelectorContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      const versionsList = this.__createVersionsList();
      versionSelectorContainer.add(versionsList);

      versionSelectorContainer.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this._addAt(versionSelectorContainer, 0);
    },

    __createVersionsList: function() {
      const versionsList = this.__versionSelector = new qx.ui.form.SelectBox().set({
        font: "text-14"
      });
      // populate versions
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const versions = osparc.utils.Services.getVersions(services, this.getService().key);
          if (versions) {
            // let lastItem = null;
            let selectedItem = null;
            versions.forEach(version => {
              const listItem = new qx.ui.form.ListItem(version).set({
                font: "text-14"
              });
              versionsList.add(listItem);
              if (this.getService().version === version) {
                selectedItem = listItem;
              }
            });
            if (selectedItem) {
              versionsList.setSelection([selectedItem]);
            }
          }
        });
      versionsList.addListener("changeSelection", e => {
        const serviceVersion = this.getSelectedVersion();
        if (serviceVersion) {
          this.__versionSelected(serviceVersion);
        }
      }, this);

      return versionsList;
    },

    __versionSelected: function(serviceVersion) {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const selectedService = osparc.utils.Services.getFromObject(services, this.getService().key, serviceVersion);
          this.setService(selectedService);
        });
    },

    getSelectedVersion: function() {
      const selection = this.__versionSelector.getSelection();
      if (selection && selection.length) {
        return selection[0].getLabel();
      }
      return null;
    }
  }
});
