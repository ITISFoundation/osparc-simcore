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

    this._setLayout(new qx.ui.layout.VBox(15));
    this.__buildLayout();

    if (studyId) {
      this.setStudyId(studyId);
    }
  },

  properties: {
    studyId: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__fetchStudy"
    },

    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet",
      apply: "__applyWallet"
    },

    patchStudy: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changePatchStudy",
    },
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
      const minHeight = 270;
      const win = osparc.ui.window.Window.popUpInWindow(resourceSelector, title, width, minHeight).set({
        clickAwayClose: false
      });

      win.set({
        maxHeight: 600
      });
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
    },

    updateName: function(studyData, name) {
      return osparc.info.StudyUtils.patchStudyData(studyData, "name", name)
        .catch(err => {
          console.error(err);
          const msg = err.message || qx.locale.Manager.tr("Something went wrong Renaming");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    updateWallet: function(studyId, walletId) {
      const params = {
        url: {
          studyId,
          walletId,
        }
      };
      return osparc.data.Resources.fetch("studies", "selectWallet", params)
        .catch(err => {
          console.error(err);
          const msg = err.message || qx.locale.Manager.tr("Error selecting Credit Account");
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
    },
  },

  members: {
    __studyData: null,
    __studyWalletId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title-layout":
          control = osparc.study.StudyOptions.createGroupBox(this.tr("Title"));
          this._addAt(control, 0);
          break;
        case "title-field":
          control = new qx.ui.form.TextField().set({
            maxWidth: 220
          });
          control.addListener("changeValue", () => this.__evaluateOpenButton());
          osparc.utils.Utils.setIdToWidget(control, "studyTitleField");
          this.getChildControl("title-layout").add(control);
          break;
        case "wallet-selector-layout":
          control = osparc.study.StudyOptions.createGroupBox(this.tr("Credit Account"));
          this._addAt(control, 1);
          break;
        case "wallet-selector":
          control = osparc.desktop.credits.Utils.createWalletSelector("read").set({
            allowGrowX: false
          });
          control.addListener("changeSelection", () => this.__evaluateOpenButton());
          this.getChildControl("wallet-selector-layout").add(control);
          break;
        case "advanced-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));
          this._addAt(control, 2, {
            flex: 1
          });
          break;
        case "advanced-checkbox":
          control = new qx.ui.form.CheckBox().set({
            label: this.tr("Advanced options"),
            value: false
          });
          this.getChildControl("advanced-layout").add(control);
          break;
        case "options-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          const scroll = new qx.ui.container.Scroll();
          this.getChildControl("advanced-checkbox").bind("value", scroll, "visibility", {
            converter: checked => checked ? "visible" : "excluded"
          });
          scroll.add(control);
          this.getChildControl("advanced-layout").add(scroll, {
            flex: 1
          });
          break;
        }
        case "loading-units-spinner":
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
          control = this.self().createGroupBox(this.tr("Tiers"));
          this.getChildControl("options-layout").add(control);
          break;
        case "study-pricing-units": {
          control = new osparc.study.StudyPricingUnits();
          const loadingImage = this.getChildControl("loading-units-spinner");
          const unitsBoxesLayout = this.getChildControl("services-resources-layout");
          const unitsLoading = () => {
            loadingImage.show();
            unitsBoxesLayout.exclude();
          };
          const unitsReady = () => {
            loadingImage.exclude();
            unitsBoxesLayout.show();
            control.getNodePricingUnits().forEach(nodePricingUnits => {
              this.bind("patchStudy", nodePricingUnits, "patchNode");
            });
          };
          unitsLoading();
          control.addListener("loadingUnits", () => unitsLoading());
          control.addListener("unitsReady", () => unitsReady());
          unitsBoxesLayout.add(control);
          break;
        }
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: "right"
          }));
          this._addAt(control, 3);
          break;
        case "cancel-button":
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text",
            font: "text-14",
            minWidth: 150,
            maxWidth: 150,
            height: 35,
            center: true
          });
          this.getChildControl("buttons-layout").addAt(control, 0);
          break;
        case "open-button":
          control = new osparc.ui.form.FetchButton(this.tr("Open")).set({
            appearance: "form-button",
            font: "text-14",
            minWidth: 150,
            maxWidth: 150,
            height: 35,
            center: true,
            enabled: false,
          });
          this.getChildControl("buttons-layout").addAt(control, 1);
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchStudy: function(studyId) {
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
          this.setStudyData(studyData);

          if (values[1] && "walletId" in values[1]) {
            this.__studyWalletId = values[1]["walletId"];
          }
          this.__buildLayout();
        });
    },

    setStudyData: function(studyData) {
      this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

      const titleField = this.getChildControl("title-field");
      titleField.setValue(this.__studyData["name"]);

      const studyPricingUnits = this.getChildControl("study-pricing-units");
      studyPricingUnits.setStudyData(this.__studyData);
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
    },

    __evaluateOpenButton: function() {
      const hasTitle = Boolean(this.getChildControl("title-field").getValue());
      const walletSelected = Boolean(this.getChildControl("wallet-selector").getSelection().length);
      const openButton = this.getChildControl("open-button");
      openButton.setEnabled(hasTitle && walletSelected);
      if (hasTitle && walletSelected) {
        osparc.utils.Utils.setIdToWidget(openButton, "openWithResources");
      } else {
        osparc.utils.Utils.removeIdAttribute(openButton);
      }
    },

    __buildLayout: function() {
      this.__buildTopSummaryLayout();
      this.__buildOptionsLayout();
      this.__buildButtons();

      this.__evaluateOpenButton();
    },

    __buildTopSummaryLayout: function() {
      const store = osparc.store.Store.getInstance();

      const titleField = this.getChildControl("title-field");
      titleField.addListener("appear", () => {
        titleField.focus();
        titleField.activate();
      });

      // Wallet Selector
      const walletSelector = this.getChildControl("wallet-selector");

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
        if (selection.length) {
          selectWallet(selection[0].walletId);
        }
      });
      const preferredWallet = store.getPreferredWallet();
      if (wallets.find(wallet => wallet.getWalletId() === parseInt(this.__studyWalletId))) {
        selectWallet(this.__studyWalletId);
      } else if (preferredWallet) {
        selectWallet(preferredWallet.getWalletId());
      } else if (!osparc.desktop.credits.Utils.autoSelectActiveWallet(walletSelector)) {
        walletSelector.setSelection([]);
      }
    },

    __buildOptionsLayout: function() {
      this.getChildControl("study-pricing-units");
    },

    __buildButtons: function() {
      // Open/Cancel buttons
      const cancelButton = this.getChildControl("cancel-button");
      cancelButton.addListener("execute", () => this.fireEvent("cancel"));

      const openButton = this.getChildControl("open-button");
      openButton.addListener("execute", () => this.__openStudy());
    },

    __openStudy: async function() {
      const openButton = this.getChildControl("open-button");
      openButton.setFetching(true);

      if (this.isPatchStudy()) {
        // first, update the name if necessary
        const titleSelection = this.getChildControl("title-field").getValue();
        if (this.__studyData["name"] !== titleSelection) {
          await this.self().updateName(this.__studyData, titleSelection);
        }

        // second, update the wallet if necessary
        const store = osparc.store.Store.getInstance();
        const walletSelection = this.getChildControl("wallet-selector").getSelection();
        if (walletSelection.length && walletSelection[0]["walletId"]) {
          const studyId = this.getStudyId();
          const walletId = walletSelection[0]["walletId"];
          this.self().updateWallet(studyId, walletId)
            .then(() => {
              store.setActiveWallet(this.getWallet());
              this.fireEvent("startStudy");
            })
            .finally(() => openButton.setFetching(false));
        } else {
          store.setActiveWallet(this.getWallet());
          this.fireEvent("startStudy");
          openButton.setFetching(false);
        }
      } else {
        this.fireEvent("startStudy");
        openButton.setFetching(false);
      }
    },
  }
});
