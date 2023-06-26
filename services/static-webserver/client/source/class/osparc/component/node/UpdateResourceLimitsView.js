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
  extend: osparc.component.node.ServiceOptionsView,

  events: {
    "limitsChanged": "qx.event.type.Event"
  },

  members: {
    _applyNode: function(node) {
      if (node.isComputational() || node.isDynamic()) {
        this.__populateLayout();
      }
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Update Service Limits")).set({
        font: "text-14"
      }));

      const resourcesLayout = osparc.info.ServiceUtils.createResourcesInfo(false);
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
          const layout = resourcesLayout.getChildren()[0];
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
                    const spinner = new qx.ui.form.Spinner(0, value, 200).set({
                      singleStep: 0.1,
                      enabled: !(resourceKey === "VRAM")
                    });
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
