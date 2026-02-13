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
      apply: "__fetchStudy",
    },

    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet",
      apply: "__applyWallet",
    },

    // indicates whether the study options will patch the study or
    // just gather the information and patch later
    patchStudy: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changePatchStudy",
    },
  },

  events: {
    "startStudy": "qx.event.type.Event",
    "cancel": "qx.event.type.Event",
  },

  statics: {
    popUpInWindow: function(resourceSelector) {
      const title = osparc.product.Utils.getStudyAlias({
        firstUpperCase: true
      }) + qx.locale.Manager.tr(" Options");
      const width = 450;
      const minHeight = 200;
      const win = osparc.ui.window.Window.popUpInWindow(resourceSelector, title, width, minHeight).set({
        clickAwayClose: false
      });
      win.set({
        maxHeight: 600
      });
      return win;
    },

    createSectionLayout: function(title) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle",
      }));
      const label = new qx.ui.basic.Label(title).set({
        font: "text-14",
        minWidth: 120,
      });
      layout.add(label);
      return layout;
    },

    createGroupBox: function(title) {
      const box = new qx.ui.groupbox.GroupBox(title).set({
        layout: new qx.ui.layout.VBox(5)
      });
      box.getChildControl("legend").set({
        font: "text-14",
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent",
        marginTop: 15,
        padding: 2,
        decorator: "no-border",
      });
      return box;
    },

    updateName: function(studyData, name) {
      return osparc.store.Study.getInstance().patchStudyData(studyData, "name", name)
        .catch(err => osparc.FlashMessenger.logError(err, qx.locale.Manager.tr("Something went wrong while renaming")));
    },

    updateWallet: function(studyId, walletId) {
      return osparc.store.Study.getInstance().selectWallet(studyId, walletId);
    },
  },

  members: {
    __studyData: null,
    __studyWalletId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title-layout":
          control = osparc.study.StudyOptions.createSectionLayout(this.tr("Title *"));
          this._add(control);
          break;
        case "title-field":
          control = new qx.ui.form.TextField().set({
            allowGrowX: true,
          });
          control.addListener("changeValue", () => this.__evaluateOpenButton());
          osparc.utils.Utils.setIdToWidget(control, "studyTitleField");
          this.getChildControl("title-layout").add(control, {
            flex: 1
          });
          break;
        case "wallet-selector-layout":
          control = osparc.study.StudyOptions.createSectionLayout(this.tr("Credit Account"));
          this._add(control);
          break;
        case "wallet-selector":
          control = osparc.desktop.credits.Utils.createWalletSelector("read").set({
            maxWidth: null,
            allowGrowX: true,
          });
          control.addListener("changeSelection", () => this.__evaluateOpenButton());
          this.getChildControl("wallet-selector-layout").add(control, {
            flex: 1
          });
          break;
        case "tags-layout":
          control = osparc.study.StudyOptions.createSectionLayout(this.tr("Tags"));
          this._add(control);
          break;
        case "current-tags-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 5));
          this.getChildControl("tags-layout").add(control, {
            flex: 1
          });
          break;
        case "tag-manager-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Add"),
            icon: "@FontAwesome5Solid/tag/12",
            allowGrowX: false,
            allowGrowY: false,
            appearance: "form-button-outlined",
            textColor: "text",
            backgroundColor: "transparent",
          });
          control.addListener("execute", () => this.__openTagsEditor());
          this.getChildControl("tags-layout").add(control);
          break;
        case "advanced-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            marginTop: 15,
            marginBottom: 15,
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "tiers-checkbox":
          control = new qx.ui.form.CheckBox().set({
            label: this.tr("Tiers & Costs"),
            value: false,
            font: "text-14",
          });
          this.getChildControl("advanced-layout").add(control);
          break;
        case "tiers-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            minHeight: 40,
          });
          const scroll = new qx.ui.container.Scroll();
          this.getChildControl("tiers-checkbox").bind("value", scroll, "visibility", {
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
          this.getChildControl("tiers-layout").add(control);
          break;
        case "study-pricing-units": {
          control = new osparc.study.StudyPricingUnits();
          const loadingImage = this.getChildControl("loading-units-spinner");
          const unitsBoxesLayout = this.getChildControl("tiers-layout");
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
          this._add(control);
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
      Promise.all([
        osparc.store.Study.getInstance().getOne(studyId),
        osparc.store.Study.getInstance().getWallet(studyId),
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

      this.__repopulateTags();

      this.getChildControl("advanced-layout").set({
        visibility: osparc.study.Utils.extractUniqueServices(this.__studyData["workbench"]).length > 0 ? "visible" : "excluded"
      });
      const studyPricingUnits = this.getChildControl("study-pricing-units");
      studyPricingUnits.setStudyData(this.__studyData);
    },

    __repopulateTags: function() {
      const currentTagsContainer = this.getChildControl("current-tags-container");
      currentTagsContainer.removeAll();
      const tagIds = this.__studyData["tags"] || [];
      const tagStore = osparc.store.Tags.getInstance();
      tagIds.forEach(tagId => {
        const tag = tagStore.getTag(tagId);
        if (tag) {
          currentTagsContainer.add(new osparc.ui.basic.Tag(tag));
        }
      });
    },

    __applyWallet: function(wallet) {
      if (wallet) {
        const walletSelector = this.getChildControl("wallet-selector");
        walletSelector.getSelectables().forEach(selectable => {
          if (selectable.walletId === wallet.getWalletId()) {
            walletSelector.setSelection([selectable]);
          }
        });
        osparc.utils.Utils.growSelectBox(walletSelector, 220);
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
      this.__addTitle();
      this.__addTags();
      this.__addWalletSelector();
      this.__addTierSelector();
      this.__addButtons();
      this.__evaluateOpenButton();
    },

    __addTitle: function() {
      const titleField = this.getChildControl("title-field");
      titleField.addListener("appear", () => {
        titleField.focus();
        titleField.activate();
      });
    },

    __addTags: function() {
      this.getChildControl("tags-layout");
      this.getChildControl("tag-manager-button");
    },

    __openTagsEditor: function() {
      const tagManager = new osparc.form.tag.TagManager(this.__studyData);
      const win = osparc.form.tag.TagManager.popUpInWindow(tagManager);
      if (this.isPatchStudy()) {
        // this is used when the project was already created and we want to update the tags
        tagManager.setLiveUpdate(true);
        tagManager.addListener("updateTags", e => {
          win.close();
          const updatedData = e.getData();
          this.__studyData["tags"] = updatedData["tags"];
          this.__repopulateTags();
        }, this);
      } else {
        // this is used when creating a new project and we want to get the selected tags
        tagManager.getChildControl("save-button").exclude();
        tagManager.getChildControl("ok-button");
        tagManager.addListener("selectedTags", e => {
          win.close();
          const updatedData = e.getData();
          this.__studyData["tags"] = updatedData["tags"];
          this.__repopulateTags();
        }, this);
      }
    },

    getSelectedTags: function() {
      return this.__studyData["tags"] || [];
    },

    __addWalletSelector: function() {
      const walletSelector = this.getChildControl("wallet-selector");

      const store = osparc.store.Store.getInstance();
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

    __addTierSelector: function() {
      this.getChildControl("study-pricing-units");
    },

    __addButtons: function() {
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
