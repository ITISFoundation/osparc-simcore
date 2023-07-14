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

qx.Class.define("osparc.component.study.ResourceSelector", {
  extend: qx.ui.core.Widget,

  construct: function(studyId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__studyId = studyId;

    this.getChildControl("loading-services-resources");
    const params = {
      url: {
        "studyId": studyId
      }
    };
    osparc.data.Resources.getOne("studies", params)
      .then(studyData => {
        this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
        this.__buildLayout();
      });
  },

  events: {
    "startStudy": "qx.event.type.Event"
  },

  statics: {
    createGroupBox: function(label) {
      const box = new qx.ui.groupbox.GroupBox(label);
      box.getChildControl("legend").set({
        font: "text-14",
        padding: 2
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent",
        padding: 2
      });
      box.setLayout(new qx.ui.layout.VBox(0));
      return box;
    },

    createToolbarRadioButton: function(label, id) {
      const rButton = new qx.ui.toolbar.RadioButton().set({
        label,
        padding: 10,
        minWidth: 35,
        center: true
      });
      rButton.id = id;
      rButton.getContentElement().setStyles({
        "border-radius": "4px"
      });
      return rButton;
    }
  },

  members: {
    __studyId: null,
    __studyData: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "loading-services-resources":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/circle-notch/48",
            alignX: "center",
            alignY: "middle",
            marginTop: 20
          });
          control.getContentElement().addClass("rotate");
          this._add(control);
          break;
        case "services-resources-layout":
          control = this.self().createGroupBox(this.tr("Select Resources"));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.__buildNodeResources();
    },

    createServiceGroup: function(serviceLabel, servicesResources) {
      const imageKeys = Object.keys(servicesResources);
      if (imageKeys && imageKeys.length) {
        const mainImageKey = imageKeys[0];
        const serviceResources = servicesResources[mainImageKey];
        if (serviceResources && "resources" in serviceResources) {
          const box = this.self().createGroupBox(serviceLabel);
          const grid = new qx.ui.layout.Grid(10, 10);
          grid.setColumnAlign(0, "center", "middle"); // resource name
          grid.setColumnAlign(1, "center", "middle"); // resource options
          grid.setColumnFlex(1, 1); // resource options
          const gridLayout = new qx.ui.container.Composite(grid);
          box.add(gridLayout);
          box.exclude();
          let i = 0;
          if ("CPU" in serviceResources["resources"]) {
            const opt1 = this.self().createToolbarRadioButton("1", 1);
            const opt2 = this.self().createToolbarRadioButton("2", 2);
            const opt3 = this.self().createToolbarRadioButton("4", 4);

            const group = new qx.ui.form.RadioGroup(opt1, opt2, opt3);
            group.setSelection([opt2]);

            const groupBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
            groupBox.add(opt1);
            groupBox.add(opt2);
            groupBox.add(opt3);

            gridLayout.add(new qx.ui.basic.Label(this.tr("CPU")), {
              column: 0,
              row: i
            });
            gridLayout.add(groupBox, {
              column: 1,
              row: i
            });
            box.show();
            i++;
          }
          if ("RAM" in serviceResources["resources"]) {
            const opt1 = this.self().createToolbarRadioButton("256 MB", 256);
            const opt2 = this.self().createToolbarRadioButton("512 MB", 512);
            const opt3 = this.self().createToolbarRadioButton("1024 MB", 1024);

            const group = new qx.ui.form.RadioGroup(opt1, opt2, opt3);
            group.setSelection([opt2]);

            const groupBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
            groupBox.add(opt1);
            groupBox.add(opt2);
            groupBox.add(opt3);

            gridLayout.add(new qx.ui.basic.Label(this.tr("RAM")), {
              column: 0,
              row: i
            });
            gridLayout.add(groupBox, {
              column: 1,
              row: i
            });
            box.show();
            i++;
          }
          return box;
        }
      }
      return null;
    },

    __buildNodeResources: function() {
      const loadingImage = this.getChildControl("loading-services-resources");
      const servicesBox = this.getChildControl("services-resources-layout");
      servicesBox.exclude();
      if ("workbench" in this.__studyData) {
        let lastServiceGroup = null;
        for (const nodeId in this.__studyData["workbench"]) {
          const node = this.__studyData["workbench"][nodeId];
          const params = {
            url: {
              studyId: this.__studyId,
              nodeId
            }
          };
          osparc.data.Resources.get("nodesInStudyResources", params)
            .then(serviceResources => {
              this._removeAll();
              this._add(servicesBox);
              const serviceGroup = this.createServiceGroup(node["label"], serviceResources);
              if (serviceGroup) {
                loadingImage.exclude();
                servicesBox.add(serviceGroup);
                // hide service name if it's a mono-service study
                if (lastServiceGroup === null) {
                  serviceGroup.getChildControl("legend").exclude();
                } else {
                  lastServiceGroup.getChildControl("legend").show();
                }
                lastServiceGroup = serviceGroup;
                servicesBox.show();
              }
            });
        }
      }
    }
  }
});
