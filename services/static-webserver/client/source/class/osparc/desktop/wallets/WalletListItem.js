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

qx.Class.define("osparc.desktop.wallets.WalletListItem", {
  extend: osparc.ui.list.ListItemWithMenu,

  construct: function() {
    this.base(arguments);

    const creditsCol = 7;
    const layout = this._getLayout();
    layout.setSpacingX(10);
    layout.setColumnWidth(creditsCol, 110);
    layout.setColumnAlign(creditsCol, "right", "middle");

    this.__buildLayout();
  },

  properties: {
    appearance: {
      refine : true,
      init : "none"
    },

    creditsAvailable: {
      check: "Number",
      nullable: false,
      apply: "__applyCreditsAvailable"
    },

    status: {
      check: ["ACTIVE", "INACTIVE"],
      init: null,
      nullable: false,
      apply: "__applyStatus"
    },

    preferredWallet: {
      check: "Boolean",
      init: null,
      nullable: false,
      apply: "__applyPreferredWallet"
    },

    autoRecharge: {
      check: "Object",
      nullable: true,
      event: "changeAutoRecharge"
    }
  },

  events: {
    "openShareWallet": "qx.event.type.Data",
    "openEditWallet": "qx.event.type.Data",
    "buyCredits": "qx.event.type.Data",
    "toggleFavourite": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnail":
          control = null
          break
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 0,
            colSpan: 2
          });
          break;
        case "subtitle":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            rich: true
          });
          this._add(control, {
            row: 1,
            column: 0,
            colSpan: 2
          });
          break;
        case "credits-indicator":
          control = new osparc.desktop.credits.CreditsIndicator().set({
            allowStretchY: false
          });
          control.getChildControl("credits-text").set({
            alignX: "right"
          });
          this._add(control, {
            row: 0,
            column: 7,
            rowSpan: 2
          });
          break;
        case "status-button":
          control = new qx.ui.form.Button().set({
            maxHeight: 30,
            width: 62,
            alignX: "center",
            alignY: "middle",
            enabled: false
          });
          control.addListener("execute", () => {
            const walletId = this.getKey();
            const store = osparc.store.Store.getInstance();
            const found = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(walletId));
            if (found) {
              // switch status
              const newStatus = found.getStatus() === "ACTIVE" ? "INACTIVE" : "ACTIVE";
              const params = {
                url: {
                  "walletId": walletId
                },
                data: {
                  "name": found.getName(),
                  "description": found.getDescription(),
                  "thumbnail": found.getThumbnail(),
                  "status": newStatus
                }
              };
              osparc.data.Resources.fetch("wallets", "put", params)
                .then(() => found.setStatus(newStatus))
                .catch(err => {
                  console.error(err);
                  const msg = err.message || (this.tr("Something went wrong updating the state"));
                  osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
                });
            }
          }, this);
          this._add(control, {
            row: 0,
            column: 4,
            rowSpan: 2
          });
          break;
        case "favourite-button":
          control = new qx.ui.form.Button().set({
            iconPosition: "right",
            width: 110, // make Primary and Secondary buttons same width
            maxHeight: 30,
            alignY: "middle"
          });
          control.addListener("execute", () => this.fireDataEvent("toggleFavourite", {
            walletId: this.getKey()
          }), this);
          this._add(control, {
            row: 0,
            column: 8,
            rowSpan: 2
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout() {
      this._removeAll();

      this.__autorechargeBtn = new qx.ui.form.ToggleButton(this.tr("Auto-recharge")).set({
        maxHeight: 30,
        alignX: "center",
        alignY: "middle",
        focusable: false
      });
      osparc.utils.Utils.setIdToWidget(this.__autorechargeBtn, "autorechargeBtn");
      this.__autorechargeBtn.addListener("execute", () => {
        const autorecharge = new osparc.desktop.credits.AutoRecharge(this.getKey());
        const win = osparc.ui.window.Window.popUpInWindow(autorecharge, "Auto-recharge", 400, 550).set({
          resizable: false,
          movable: false
        });
        autorecharge.addListener("close", () => win.close());
        autorecharge.addListener("addNewPaymentMethod", () => {
          win.close()
          const billingCenter = osparc.desktop.credits.BillingCenterWindow.openWindow()
          billingCenter.openPaymentMethods()
        })
        // Revert default execute action (toggle the buttons's value)
        this.__autorechargeBtn.toggleValue();
      });
      this.bind("autoRecharge", this.__autorechargeBtn, "value", {
        converter: ar => ar ? ar.enabled : false
      });
      this.__autorechargeBtn.bind("value", this.__autorechargeBtn, "label", {
        converter: value => value ? this.tr("Auto-recharge: ON") : this.tr("Auto-recharge: OFF")
      });
      this._add(this.__autorechargeBtn, {
        // Takes the status button place for the moment
        row: 0,
        column: 5,
        rowSpan: 2
      });

      this.__shareButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/users/14").set({
        maxHeight: 30,
        alignX: "center",
        alignY: "middle",
        focusable: false,
        visibility: this.__canIWrite() ? "visible" : "excluded",
      });
      this.__shareButton.addListener("execute", () => this.fireDataEvent("openShareWallet", this.getKey()));
      this._add(this.__shareButton, {
        row: 0,
        column: 4,
        rowSpan: 2
      });
    },

    __applyCreditsAvailable: function(creditsAvailable) {
      if (creditsAvailable !== null) {
        const creditsIndicator = this.getChildControl("credits-indicator");
        creditsIndicator.setCreditsAvailable(creditsAvailable);
      }
    },

    __canIWrite: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const accessRightss = this.getAccessRights();
      const found = accessRightss && accessRightss.find(ar => ar["gid"] === myGid);
      if (found) {
        return found["write"];
      }
      return false;
    },

    // overridden
    _applyAccessRights: function(accessRights) {
      this.__buildLayout();
      this.base(arguments, accessRights);
      this.__buyBtn = new qx.ui.form.Button().set({
        label: this.tr("Buy Credits"),
        icon: "@FontAwesome5Solid/dollar-sign/16",
        maxHeight: 30,
        alignY: "middle",
        visibility: this.__canIWrite() ? "visible" : "excluded",
      });
      osparc.utils.Utils.setIdToWidget(this.__buyBtn, "buyCreditsBtn");
      this.bind("accessRights", this.__buyBtn, "enabled", {
        converter: aR => {
          const myAr = osparc.data.model.Wallet.getMyAccessRights(aR);
          return Boolean(myAr && myAr.write);
        }
      });
      this.__buyBtn.addListener("execute", () => this.fireDataEvent("buyCredits", {
        walletId: this.getKey()
      }), this);
      this._add(this.__buyBtn, {
        row: 0,
        column: 6,
        rowSpan: 2
      });
      this.__autorechargeBtn.setVisibility(this.__canIWrite() ? "visible" : "excluded");
    },

    // overridden
    _setRole: function() {
      const accessRightss = this.getAccessRights();
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const found = accessRightss && accessRightss.find(ar => ar["gid"] === myGid);
      if (found) {
        const role = this.getChildControl("role");
        if (found["write"]) {
          role.setValue(osparc.data.Roles.WALLET[2].label);
        } else if (found["read"]) {
          role.setValue(osparc.data.Roles.WALLET[1].label);
        }
      }
    },

    // overridden
    _getOptionsMenu: function() {
      let menu = null;
      const accessRightss = this.getAccessRights();
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const found = accessRightss && accessRightss.find(ar => ar["gid"] === myGid);
      if (found && found["write"]) {
        const optionsMenu = this.getChildControl("options");
        optionsMenu.show();

        menu = new qx.ui.menu.Menu().set({
          position: "bottom-right"
        });
        const editWalletButton = new qx.ui.menu.Button(this.tr("Edit details..."));
        editWalletButton.addListener("execute", () => this.fireDataEvent("openEditWallet", this.getKey()));
        menu.add(editWalletButton);
      }
      return menu;
    },

    // overridden
    _applyThumbnail: function(value) {
    },

    __applyStatus: function(status) {
      if (status) {
        const statusButton = this.getChildControl("status-button");
        statusButton.set({
          icon: status === "ACTIVE" ? "@FontAwesome5Solid/toggle-on/16" : "@FontAwesome5Solid/toggle-off/16",
          label: status === "ACTIVE" ? this.tr("ON") : this.tr("OFF"),
          toolTipText: status === "ACTIVE" ? this.tr("Credit Account enabled") : this.tr("Credit Account blocked"),
          enabled: this.__canIWrite(),
          visibility: "excluded" // excluded until the backed implements it
        });
      }
    },

    __applyPreferredWallet: function(isPreferredWallet) {
      const favouriteButton = this.getChildControl("favourite-button");
      favouriteButton.setBackgroundColor("transparent");
      const favouriteButtonIcon = favouriteButton.getChildControl("icon");
      if (isPreferredWallet) {
        favouriteButton.set({
          toolTipText: this.tr("Currently being used"),
          icon: "@FontAwesome5Solid/check-circle/20"
        });
        favouriteButtonIcon.setTextColor("strong-main");
      } else {
        favouriteButton.set({
          toolTipText: this.tr("Switch to this Credit Account"),
          icon: "@FontAwesome5Solid/circle/20"
        });
        favouriteButtonIcon.setTextColor("text");
      }
    },

    excludeShareButton: function() {
      if (this.__shareButton) {
        this.__shareButton.exclude()
      }
    }
  }
});
