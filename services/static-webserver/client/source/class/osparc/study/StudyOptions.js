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

qx.Class.define("osparc.study.StudyOptions", {
  extend: qx.ui.core.Widget,

  construct: function(studyId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      minWidth: 300
    });

    this.__studyId = studyId;

    const params = {
      url: {
        studyId
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
      const minHeight = 200;
      const maxHeight = 600;
      const win = osparc.ui.window.Window.popUpInWindow(resourceSelector, title, width, minHeight).set({
        maxHeight,
        clickAwayClose: false
      });
      win.center();
      win.open();
      return win;
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
        case "wallet-selector-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("top-summary-layout").add(control);
          break;
        case "wallet-selector-label":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Credit Account:"),
            font: "text-14"
          });
          this.getChildControl("wallet-selector-layout").add(control);
          break;
        case "wallet-selector":
          control = osparc.desktop.credits.Utils.createWalletSelector("read").set({
            width: 150
          });
          this.getChildControl("wallet-selector-layout").add(control);
          break;
        case "credits-left-view":
          control = this.__getCreditsIndicator();
          this.getChildControl("top-summary-layout").add(control);
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
            alignX: "right"
          }));
          this.getChildControl("top-summary-layout").add(control, {
            flex: 1
          });
          break;
        case "open-button":
          control = new qx.ui.form.Button(this.tr("Open")).set({
            appearance: "strong-button",
            font: "text-14",
            maxWidth: 150,
            height: 35,
            center: true
          });
          osparc.utils.Utils.setIdToWidget(control, "openWithResources");
          this.getChildControl("buttons-layout").add(control);
          break;
        case "cancel-button":
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            font: "text-14",
            maxWidth: 150,
            height: 35,
            center: true
          });
          this.getChildControl("buttons-layout").add(control);
          break;
        case "advanced-options":
          control = new qx.ui.form.CheckBox().set({
            label: this.tr("Advanced options"),
            value: false
          });
          this._addAt(control, 1);
          break;
        case "options-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
            padding: 10
          });
          this.getChildControl("advanced-options").bind("value", control, "visibility", {
            converter: checked => checked ? "visible" : "excluded"
          });
          this._addAt(control, 2, {
            flex: 1
          });
          break;
        case "loading-units-spinner":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/circle-notch/48",
            alignX: "center",
            alignY: "middle",
            marginTop: 20
          });
          control.getContentElement().addClass("rotate");
          this.getChildControl("options-layout").add(control, {
            flex: 1
          });
          break;
        case "services-resources-layout":
          control = this.self().createGroupBox(this.tr("Select Resources"));
          this.getChildControl("options-layout").add(control, {
            flex: 1
          });
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

      this.getChildControl("open-button").setEnabled(Boolean(wallet));
    },

    __buildLayout: function() {
      this.__buildTopSummaryLayout();
      this.__buildOptionsLayout();
    },

    __buildOptionsLayout: function() {
      this.__buildPricingPlans();
    },

    __buildPricingPlans: function() {
      const loadingImage = this.getChildControl("loading-units-spinner");
      const unitsBoxesLayout = this.getChildControl("services-resources-layout");
      const unitsLoading = () => {
        loadingImage.show();
        unitsBoxesLayout.exclude();
      };
      const unitsReady = () => {
        loadingImage.exclude();
        unitsBoxesLayout.show();
      };
      unitsLoading();
      const studyPricingUnits = new osparc.study.StudyPricingUnits(this.__studyData);
      studyPricingUnits.addListener("loadingUnits", () => unitsLoading());
      studyPricingUnits.addListener("unitsReady", () => unitsReady());
      unitsBoxesLayout.add(studyPricingUnits);
    },

    __buildTopSummaryLayout: function() {
      const store = osparc.store.Store.getInstance();

      // Wallet Selector
      this._createChildControlImpl("wallet-selector-label");
      const walletSelector = this.getChildControl("wallet-selector");
      this._createChildControlImpl("credits-left-view");

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
      const preferredWallet = store.getPreferredWallet();
      if (this.__projectWalletId) {
        selectWallet(this.__projectWalletId);
      } else if (preferredWallet) {
        selectWallet(preferredWallet.getWalletId());
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
              const msg = err.message || this.tr("Error selecting Credit Account");
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

    __getCreditsIndicator: function() {
      const creditsIndicator = new osparc.desktop.credits.CreditsIndicator();
      this.bind("wallet", creditsIndicator, "wallet");
      return creditsIndicator;
    }
  }
});
