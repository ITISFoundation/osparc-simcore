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

qx.Class.define("osparc.study.ResourceSelector", {
  extend: qx.ui.core.Widget,

  construct: function(studyId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__studyId = studyId;

    this.getChildControl("loading-services-resources");
    const params = {
      url: {
        "studyId": studyId
      }
    };
    Promise.all([
      osparc.data.Resources.getOne("studies", params),
      osparc.data.Resources.fetch("studies", "getWallet", params)
    ])
      .then(values => {
        const studyData = values[0];
        this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
        if (values[1] && "walletId" in values[1]) {
          this.__projectWalletId = values[1]["walletId"];
        }
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
    popUpInWindow: function(resourceSelector) {
      const title = osparc.product.Utils.getStudyAlias({
        firstUpperCase: true
      }) + qx.locale.Manager.tr(" Options");
      const width = 550;
      const height = 400;
      const win = osparc.ui.window.Window.popUpInWindow(resourceSelector, title, width, height);
      win.center();
      win.open();
      return win;
    },

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
        marginTop: 15,
        padding: 2
      });
      box.setLayout(new qx.ui.layout.VBox(5));
      return box;
    }
  },

  members: {
    __studyId: null,
    __studyData: null,
    __projectWalletId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "top-summary-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(30));
          this._addAt(control, 0);
          break;
        case "options-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
            minWidth: 300
          });
          this._addAt(control, 1, {
            flex: 1
          });
          break;
        case "loading-services-resources":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/circle-notch/48",
            alignX: "center",
            alignY: "middle",
            marginTop: 20
          });
          control.getContentElement().addClass("rotate");
          this.getChildControl("options-layout").add(control);
          break;
        case "services-resources-layout":
          control = this.self().createGroupBox(this.tr("Select Resources"));
          this.getChildControl("options-layout").add(control);
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            minWidth: 100,
            maxWidth: 150
          });
          this.getChildControl("top-summary-layout").add(control, {
            flex: 1
          });
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
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            maxWidth: 150
          });
          this.getChildControl("top-summary-layout").add(control, {
            flex: 1
          });
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
          this.getChildControl("top-summary-layout").add(control, {
            flex: 1
          });
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

      // OM: puppeteer has no wallets. Enable it when BE is ready
      // this.getChildControl("open-button").setEnabled(Boolean(wallet));
    },

    __buildLayout: function() {
      this.__buildTopSummaryLayout();
      this.__buildOptionsLayout();
    },

    createTierButtonsGroup: function(serviceLabel, servicesResources, advancedCB) {
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
            const smallButton = new osparc.study.TierButton(smInfo);
            const mediumButton = new osparc.study.TierButton(mdInfo);
            const largeButton = new osparc.study.TierButton(lgInfo);
            [
              smallButton,
              mediumButton,
              largeButton
            ].forEach(btn => {
              advancedCB.bind("value", btn, "advanced");
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
                  value: serviceLabel + ": " + btn.getTierInfo().price
                });
              }
            }));
            // medium by default
            mediumButton.execute();
          }
          return machinesLayout;
        }
      }
      return null;
    },

    __buildOptionsLayout: function() {
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
              this.getChildControl("options-layout")._removeAll();
              this.getChildControl("options-layout").add(servicesBox);
              const advancedCB = new qx.ui.form.CheckBox().set({
                label: this.tr("Advanced"),
                value: false
              });
              servicesBox.add(advancedCB);
              const serviceGroup = this.createTierButtonsGroup(node["label"], serviceResources, advancedCB);
              if (serviceGroup) {
                loadingImage.exclude();
                servicesBox.add(serviceGroup);
                servicesBox.show();
              }
            });
        }
      }
    },

    __buildTopSummaryLayout: function() {
      const store = osparc.store.Store.getInstance();

      // Wallet Selector
      const walletSelector = this.getChildControl("wallet-selector");
      this._createChildControlImpl("credits-left-view");

      // Credits Summary
      const summaryLayout = this.getChildControl("summary-layout");
      summaryLayout.add(new qx.ui.basic.Label(this.tr("Total Credits/h:")).set({
        font: "text-14"
      }));
      this.getChildControl("summary-label");

      const wallets = store.getWallets();
      const selectWallet = walletId => {
        const found = wallets.find(wallet => wallet.getWalletId() === parseInt(walletId));
        if (found) {
          this.setWallet(found);
        } else {
          this.setWallet(null);
        }
      };
      walletSelector.addListener("changeSelection", e => {
        const selection = e.getData();
        selectWallet(selection[0].walletId);
      });
      const favWallet = osparc.desktop.credits.Utils.getPreferredWallet();
      if (this.__projectWalletId) {
        selectWallet(this.__projectWalletId);
      } else if (favWallet) {
        selectWallet(favWallet.getWalletId());
      } else if (!osparc.desktop.credits.Utils.autoSelectActiveWallet(walletSelector)) {
        walletSelector.setSelection([]);
      }

      // Open/Cancel buttons
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
              osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
            });
        } else {
          store.setActiveWallet(this.getWallet());
          this.fireEvent("startStudy");
        }
      });

      const cancelButton = this.getChildControl("cancel-button");
      cancelButton.addListener("execute", () => this.fireEvent("cancel"));
    },

    __getCreditsLeftView: function() {
      const creditsLeftView = new osparc.desktop.credits.CreditsLabel();
      this.bind("wallet", creditsLeftView, "wallet");
      return creditsLeftView;
    }
  }
});
