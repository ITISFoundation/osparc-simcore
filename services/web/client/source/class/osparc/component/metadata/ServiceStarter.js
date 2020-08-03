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


qx.Class.define("osparc.component.metadata.ServiceStarter", {
  extend: osparc.component.metadata.ServiceDetails,

  /**
    * @param serviceData {Object} Service metadata
    */
  construct: function(serviceData) {
    this.base(arguments, serviceData);

    this.__createToolbox();

    this.addListener("changeService", e => {
      const newServ = e.getData();
      const oldServ = e.getOldData();
      if (oldServ && oldServ.key === newServ.key) {
        return;
      }
      this.__createToolbox();
    }, this);
  },

  events: {
    "startService": "qx.event.type.Data"
  },

  members: {
    __toolBox: null,
    __versionsUIBox: null,

    __createToolbox: function() {
      const toolboxContainer = this.__toolBox = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      const versionsList = this.__createVersionsList();
      toolboxContainer.add(versionsList);

      toolboxContainer.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const openButton = new qx.ui.form.Button(this.tr("Open")).set({
        appearance: "md-button"
      });
      openButton.addListener("execute", () => {
        const data = {
          "serviceKey": this.getService().key,
          "serviceVersion": this.__getSelectedVersion()
        };
        this.fireDataEvent("startService", data);
      });
      toolboxContainer.add(openButton);

      this._addAt(toolboxContainer, 0);
    },

    __createVersionsList: function() {
      const versionsList = this.__versionsUIBox = new qx.ui.form.SelectBox().set({
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
              // this.__versionSelected(lastItem.getLabel());
            }
          }
        });
      versionsList.addListener("changeSelection", e => {
        const serviceVersion = this.__getSelectedVersion();
        if (serviceVersion) {
          this.__versionSelected(serviceVersion);
        }
      }, this);

      return versionsList;
    },

    __getSelectedVersion: function() {
      const selection = this.__versionsUIBox.getSelection();
      if (selection && selection.length) {
        return selection[0].getLabel();
      }
      return null;
    },

    __versionSelected: function(serviceVersion) {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const selectedService = osparc.utils.Services.getFromObject(services, this.getService().key, serviceVersion);
          this.setService(selectedService);
        });
    }
  }
});
