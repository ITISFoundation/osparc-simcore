/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.node.UpdateResourceLimitsView", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox(5));

    if (node) {
      this.setNode(node);
    }
  },

  events: {
    "limitsChanged": "qx.event.type.Event"
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "__applyNode"
    }
  },

  members: {
    __applyNode: function(node) {
      if (node.isComputational() || node.isDynamic()) {
        this.__populateLayout();
      }
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Update Service Limits")).set({
        font: "text-14"
      }));

      const resourcesLayout = osparc.info.ServiceUtils.createResourcesInfo();
      this._add(resourcesLayout);

      const node = this.getNode();
      const params = {
        url: {
          studyId: node.getStudy().getUuid(),
          nodeId: node.getNodeId()
        }
      };
      osparc.data.Resources.get("nodesInStudyResources", params)
        .then(serviceResources => {
          resourcesLayout.show();
          const layout = resourcesLayout.getChildren()[1];
          let row = 1;
          Object.entries(serviceResources).forEach(([imageName, imageInfo]) => {
            layout.add(new qx.ui.basic.Label(imageName).set({
              font: "text-13"
            }), {
              row,
              column: 0
            });
            if ("resources" in imageInfo) {
              const resourcesInfo = imageInfo["resources"];
              Object.keys(resourcesInfo).forEach(resourceKey => {
                let column = 1;
                const resourceInfo = resourcesInfo[resourceKey];
                let label = resourceKey;
                if (resourceKey === "RAM") {
                  label += " (GB)";
                }
                layout.add(new qx.ui.basic.Label(label).set({
                  font: "text-13"
                }), {
                  row,
                  column
                });
                column++;
                Object.keys(osparc.info.ServiceUtils.RESOURCES_INFO).forEach(resourceInfoKey => {
                  if (resourceInfoKey in resourceInfo) {
                    let value = resourceInfo[resourceInfoKey];
                    if (resourceKey === "RAM") {
                      value = osparc.utils.Utils.bytesToGB(value);
                    }
                    const spinner = new qx.ui.form.Spinner(0, value, 300);
                    spinner.setSingleStep(0.1);
                    layout.add(spinner, {
                      row,
                      column
                    });
                    column++;
                  }
                });
                row++;
              });
            }
          });
        })
        .catch(err => console.error(err));

      return resourcesLayout;
    }
  }
});
