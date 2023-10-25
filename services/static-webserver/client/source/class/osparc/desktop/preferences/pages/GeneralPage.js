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


qx.Class.define("osparc.desktop.preferences.pages.GeneralPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/cogs/24";
    const title = this.tr("General Settings");
    this.base(arguments, title, iconSrc);

    const walletIndicatorSettings = this.__createCreditsIndicatorSettings();
    this.add(walletIndicatorSettings);
  },

  statics: {
    patchPreference: function(preferenceId, preferenceField, newValue) {
      const preferencesSettings = osparc.Preferences.getInstance();

      const oldValue = preferencesSettings.get(preferenceId);
      if (newValue === oldValue) {
        return;
      }

      preferenceField.setEnabled(false);
      osparc.Preferences.patchPreference(preferenceId, newValue)
        .then(() => preferencesSettings.set(preferenceId, newValue))
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(err.message, "ERROR");
          preferenceField.setValue(oldValue);
        })
        .finally(() => preferenceField.setEnabled(true));
    }
  },

  members: {
    __createCreditsIndicatorSettings: function() {
      // layout
      const box = this._createSectionBox(this.tr("Credits Indicator"));

      const label = this._createHelpLabel(this.tr(
        "Choose how you want the Credits Indicator to look like and when it is shown:"
      ));
      box.add(label);

      const form = new qx.ui.form.Form();

      const preferencesSettings = osparc.Preferences.getInstance();

      const walletIndicatorModeSB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      [{
        id: "both",
        label: "Both"
      }, {
        id: "text",
        label: "Text"
      }, {
        id: "bar",
        label: "Bar"
      }].forEach(options => {
        const lItem = new qx.ui.form.ListItem(options.label, null, options.id);
        walletIndicatorModeSB.add(lItem);
      });
      const value = preferencesSettings.getWalletIndicatorMode();
      walletIndicatorModeSB.getSelectables().forEach(selectable => {
        if (selectable.getModel() === value) {
          walletIndicatorModeSB.setSelection([selectable]);
        }
      });
      walletIndicatorModeSB.addListener("changeValue", e => {
        const selectable = e.getData();
        this.self().patchPreference("walletIndicatorMode", walletIndicatorModeSB, selectable.getModel());
      });
      form.add(walletIndicatorModeSB, this.tr("Indicator mode"));

      const walletIndicatorVisibilitySB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      [{
        id: "always",
        label: "Always"
      }, {
        id: "warning",
        label: "Warning"
      }].forEach(options => {
        const lItem = new qx.ui.form.ListItem(options.label, null, options.id);
        walletIndicatorVisibilitySB.add(lItem);
      });
      const value2 = preferencesSettings.getWalletIndicatorVisibility();
      walletIndicatorVisibilitySB.getSelectables().forEach(selectable => {
        if (selectable.getModel() === value2) {
          walletIndicatorVisibilitySB.setSelection([selectable]);
        }
      });
      walletIndicatorVisibilitySB.addListener("changeValue", e => {
        const selectable = e.getData();
        this.self().patchPreference("walletIndicatorVisibility", walletIndicatorVisibilitySB, selectable.getModel());
      });
      form.add(walletIndicatorVisibilitySB, this.tr("Show it"));

      box.add(new qx.ui.form.renderer.Single(form));

      return box;
    }
  }
});
