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

    this._setLayout(new qx.ui.layout.HBox(10));

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

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet",
      apply: "__applyWallet"
    }
  },

  events: {
    "startStudy": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  statics: {
    getMachineInfo: function(machineId) {
      switch (machineId) {
        case "sm":
          return {
            id: "sm",
            title: qx.locale.Manager.tr("Small"),
            resources: {},
            price: 4
          };
        case "md":
          return {
            id: "md",
            title: qx.locale.Manager.tr("Medium"),
            resources: {},
            price: 7
          };
        case "lg":
          return {
            id: "lg",
            title: qx.locale.Manager.tr("Large"),
            resources: {},
            price: 10
          };
      }
      return null;
    },

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
      box.setLayout(new qx.ui.layout.VBox(5));
      return box;
    },

    createMachineToggleButton: function(machineInfo) {
      const toFixedIfNecessary = (value, dp) => Number(parseFloat(value).toFixed(dp));
      const rButton = new qx.ui.form.ToggleButton().set({
        padding: 10,
        minWidth: 120,
        maxWidth: 120,
        center: true
      });
      // eslint-disable-next-line no-underscore-dangle
      rButton._setLayout(new qx.ui.layout.VBox(5));
      rButton.info = machineInfo;
      // eslint-disable-next-line no-underscore-dangle
      rButton._add(new qx.ui.basic.Label().set({
        value: machineInfo.title,
        font: "text-16"
      }));
      Object.keys(machineInfo.resources).forEach(resourceKey => {
        // eslint-disable-next-line no-underscore-dangle
        rButton._add(new qx.ui.basic.Label().set({
          value: resourceKey + ": " + toFixedIfNecessary(machineInfo.resources[resourceKey]),
          font: "text-12"
        }));
      });
      // eslint-disable-next-line no-underscore-dangle
      rButton._add(new qx.ui.basic.Label().set({
        value: qx.locale.Manager.tr("Credits/h") + ": " + machineInfo.price,
        font: "text-14"
      }));
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
        case "left-main-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
            minWidth: 300
          });
          this._addAt(control, 0, {
            flex: 1
          });
          break;
        case "right-main-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
            minWidth: 120
          });
          this._addAt(control, 1);
          break;
        case "loading-services-resources":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/circle-notch/48",
            alignX: "center",
            alignY: "middle",
            marginTop: 20
          });
          control.getContentElement().addClass("rotate");
          this.getChildControl("left-main-layout").add(control);
          break;
        case "services-resources-layout":
          control = this.self().createGroupBox(this.tr("Select Resources"));
          this.getChildControl("left-main-layout").add(control);
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("right-main-layout").add(control);
          break;
        case "open-button":
          control = new qx.ui.form.Button(this.tr("Open")).set({
            appearance: "strong-button",
            font: "text-14",
            alignX: "right",
            height: 35,
            width: 70,
            center: true
          });
          osparc.utils.Utils.setIdToWidget(control, "openWithResources");
          this.getChildControl("buttons-layout").add(control);
          break;
        case "cancel-button":
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            font: "text-14",
            alignX: "right",
            height: 35,
            width: 70,
            center: true
          });
          this.getChildControl("buttons-layout").add(control);
          break;
        case "wallet-selector-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("right-main-layout").add(control);
          break;
        case "wallet-selector":
          control = osparc.desktop.credits.Utils.createWalletSelector("read", true, true);
          this.getChildControl("wallet-selector-layout").add(control);
          break;
        case "credits-left-view":
          control = this.__getCreditsLeftView();
          this.getChildControl("wallet-selector-layout").add(control);
          break;
        case "summary-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("right-main-layout").add(control);
          break;
        case "summary-label":
          control = new qx.ui.basic.Label();
          this.getChildControl("summary-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyWallet: function(wallet) {
      if (wallet) {
        const walletSelector = this.getChildControl("wallet-selector");
        walletSelector.getSelectables().forEach(selectable => {
          if (selectable.walletId === wallet.getWalletId()) {
            walletSelector.setSelection([selectable]);
          }
        });
      }

      // OM: puppeteer has no walelts. Enable it when BE is ready
      // this.getChildControl("open-button").setEnabled(Boolean(wallet));
    },

    __buildLayout: function() {
      this.__buildRightColumn();
      this.__buildLeftColumn();
    },

    createServiceGroup: function(serviceLabel, servicesResources) {
      const imageKeys = Object.keys(servicesResources);
      if (imageKeys && imageKeys.length) {
        // hack to show "s4l-core"
        const mainImageKey = imageKeys.length > 1 ? imageKeys[1] : imageKeys[0];
        const serviceResources = servicesResources[mainImageKey];
        if (serviceResources && "resources" in serviceResources) {
          const machinesLayout = this.self().createGroupBox(serviceLabel);
          machinesLayout.setLayout(new qx.ui.layout.HBox(5));
          machinesLayout.exclude();

          const smInfo = this.self().getMachineInfo("sm");
          const mdInfo = this.self().getMachineInfo("md");
          const lgInfo = this.self().getMachineInfo("lg");
          if ("CPU" in serviceResources["resources"]) {
            const lgValue = serviceResources["resources"]["CPU"]["limit"];
            smInfo["resources"]["CPU"] = lgValue/4;
            mdInfo["resources"]["CPU"] = lgValue/2;
            lgInfo["resources"]["CPU"] = lgValue;
          }
          if ("RAM" in serviceResources["resources"]) {
            const lgValue = serviceResources["resources"]["RAM"]["limit"];
            smInfo["resources"]["RAM"] = osparc.utils.Utils.bytesToGB(lgValue/4);
            mdInfo["resources"]["RAM"] = osparc.utils.Utils.bytesToGB(lgValue/2);
            lgInfo["resources"]["RAM"] = osparc.utils.Utils.bytesToGB(lgValue);
          }
          if ("VRAM" in serviceResources["resources"]) {
            const lgValue = serviceResources["resources"]["VRAM"]["limit"];
            smInfo["resources"]["VRAM"] = lgValue;
            mdInfo["resources"]["VRAM"] = lgValue;
            lgInfo["resources"]["VRAM"] = lgValue;
          }
          if (Object.keys(lgInfo["resources"]).length) {
            const buttons = [];
            const smallButton = this.self().createMachineToggleButton(smInfo);
            const mediumButton = this.self().createMachineToggleButton(mdInfo);
            const largeButton = this.self().createMachineToggleButton(lgInfo);
            [
              smallButton,
              mediumButton,
              largeButton
            ].forEach(btn => {
              buttons.push(btn);
              machinesLayout.add(btn);
            });
            machinesLayout.show();

            const buttonSelected = button => {
              buttons.forEach(btn => {
                if (btn !== button) {
                  btn.setValue(false);
                }
              });
            };
            buttons.forEach(btn => btn.addListener("execute", () => buttonSelected(btn)));
            buttons.forEach(btn => btn.addListener("changeValue", e => {
              if (e.getData()) {
                this.getChildControl("summary-label").set({
                  value: serviceLabel + ": " + btn.info.price
                });
              }
            }));
            // small by default
            smallButton.execute();
          }
          return machinesLayout;
        }
      }
      return null;
    },

    __buildLeftColumn: function() {
      this.__buildNodeResources();
    },

    __buildNodeResources: function() {
      const loadingImage = this.getChildControl("loading-services-resources");
      const servicesBox = this.getChildControl("services-resources-layout");
      servicesBox.exclude();
      if ("workbench" in this.__studyData) {
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
              // eslint-disable-next-line no-underscore-dangle
              this.getChildControl("left-main-layout")._removeAll();
              this.getChildControl("left-main-layout").add(servicesBox);
              const serviceGroup = this.createServiceGroup(node["label"], serviceResources);
              if (serviceGroup) {
                loadingImage.exclude();
                servicesBox.add(serviceGroup);
                servicesBox.show();
              }
            });
        }
      }
    },

    __buildRightColumn: function() {
      const store = osparc.store.Store.getInstance();

      const openButton = this.getChildControl("open-button");
      openButton.addListener("execute", () => {
        const selection = this.getChildControl("wallet-selector").getSelection();
        if (selection.length && selection[0]["walletId"]) {
          const params = {
            url: {
              "studyId": this.__studyData["uuid"],
              "walletId": selection[0]["walletId"]
            }
          };
          osparc.data.Resources.fetch("studies", "selectWallet", params)
            .then(() => {
              store.setActiveWallet(this.getWallet());
              this.fireEvent("startStudy");
            })
            .catch(err => {
              console.error(err);
              const msg = err.message || this.tr("Error selecting Wallet");
              osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
            });
        } else {
          store.setActiveWallet(this.getWallet());
          this.fireEvent("startStudy");
        }
      });

      const cancelButton = this.getChildControl("cancel-button");
      cancelButton.addListener("execute", () => this.fireEvent("cancel"));

      const walletSelector = this.getChildControl("wallet-selector");
      this.getChildControl("credits-left-view");

      const summaryLayout = this.getChildControl("summary-layout");
      summaryLayout.add(new qx.ui.basic.Label(this.tr("Total Credits/h:")).set({
        font: "text-14"
      }));
      this.getChildControl("summary-label");

      walletSelector.addListener("changeSelection", e => {
        const selection = e.getData();
        const found = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(selection[0].walletId));
        if (found) {
          this.setWallet(found);
        } else {
          this.setWallet(null);
        }
      });
      walletSelector.setSelection([]);
    },

    __getCreditsLeftView: function() {
      const creditsLeftView = new osparc.desktop.credits.CreditsIndicatorWText();
      this.bind("wallet", creditsLeftView, "wallet");
      return creditsLeftView;
    }
  }
});
