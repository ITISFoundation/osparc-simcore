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
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const preferences = osparc.Preferences.getInstance();

    // each setting is added in isolation, so that a faulty preference value
    // only breaks its own section instead of the whole My Account window
    if (osparc.product.Utils.isLocaleEnabled() && osparc.utils.LanguageManager.isSwitchUseful()) {
      this.__addSetting(() => this.__addLanguageSetting());
    }

    if (osparc.store.StaticInfo.isBillableProduct()) {
      this.__addSetting(() => this.__addCreditsIndicatorSettings());
    }

    if (preferences.getLowDiskSpaceThreshold()) {
      this.__addSetting(() => this.__addLowDiskSpaceSetting());
    }

    this.__defaultStudyTagsIndex = this._getChildren().length;
    this.__addSetting(() => this.refreshDefaultStudyTagsSetting());

    if (osparc.store.StaticInfo.isBillableProduct()) {
      this.__addSetting(() => this.__addInactivitySetting());
    }

    if (osparc.product.Utils.isS4LProduct() || osparc.product.Utils.isProduct("s4llite")) {
      this.__addSetting(() => this.__addS4LUserPrivacySettings());
    }
  },

  members: {
    __defaultStudyTagsBox: null,
    __defaultStudyTagsIndex: 0,
    __defaultStudyTagsLoaded: false,
    __defaultStudyTagsLoad: null,
    __defaultStudyTagsSaving: false,
    __defaultStudyTagsRefreshPending: false,

    getChildrenCount: function() {
      return this._getChildren().length;
    },

    __addSetting: function(addSettingCbk) {
      try {
        addSettingCbk();
      } catch (err) {
        console.error("Failed to add setting to General preferences page", err);
      }
    },

    __addLanguageSetting: function() {
      const box = new osparc.widget.SectionBox(this.tr("Language"));

      box.addHelper(this.tr("Languages marked (Beta) are previews that may contain inaccuracies."));

      const form = new qx.ui.form.Form();

      const languageSB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      languageSB.getChildControl("arrow").syncAppearance(); // force sync to show the arrow
      osparc.utils.LanguageManager.getAvailableLocales().forEach(localeCode => {
        // qx.ui.form.ListItem is an Atom, not a Composite: it cannot host child
        // widgets, so the beta marker goes into the label text itself.
        // Language labels are kept in their original language on purpose, and
        // "Beta" is a widely understood marker, so neither is translated here.
        const isBeta = osparc.utils.LanguageManager.isLocaleBeta(localeCode);
        const label = osparc.utils.LanguageManager.getLocaleLabel(localeCode);
        const labelWithBeta = isBeta ? `${label} (Beta)` : label;
        const lItem = new qx.ui.form.ListItem(labelWithBeta, null, localeCode);
        if (isBeta) {
          lItem.setToolTipText(this.tr("This translation is a preview and may contain inaccuracies"));
        }
        languageSB.add(lItem);
      });

      // qooxdoo gives SelectBox a fixed default width: grow it to fit the
      // longest option (plus room for the dropdown arrow and field padding)
      const widestItemWidth = languageSB.getChildren().reduce(
        (max, item) => Math.max(max, item.getSizeHint().width),
        0
      );
      languageSB.set({
        minWidth: widestItemWidth + 20
      });

      const currentLocale = osparc.utils.LanguageManager.getUserLocale();
      languageSB.getSelectables().forEach(selectable => {
        if (selectable.getModel() === currentLocale) {
          languageSB.setSelection([selectable]);
        }
      });

      languageSB.addListener("changeValue", e => {
        const selectable = e.getData();
        if (selectable) {
          const localeCode = selectable.getModel();
          osparc.utils.LanguageManager.setLocale(localeCode);
          osparc.utils.LanguageManager.patchLocale(localeCode);
        }
      });
      form.add(languageSB, this.tr("Language"));

      box.add(new qx.ui.form.renderer.Single(form));

      this._add(box);
    },

    __addCreditsIndicatorSettings: function() {
      const box = new osparc.widget.SectionBox(this.tr("Credits Indicator"));

      const form = new qx.ui.form.Form();

      const preferencesSettings = osparc.Preferences.getInstance();

      const walletIndicatorVisibilitySB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      walletIndicatorVisibilitySB.getChildControl("arrow").syncAppearance(); // force sync to show the arrow
      [{
        id: "always",
        label: this.tr("Always")
      }, {
        id: "warning",
        label: this.tr("Warning")
      }].forEach(options => {
        const lItem = new qx.ui.form.ListItem(options.label, null, options.id);
        walletIndicatorVisibilitySB.add(lItem);
      });
      const value = preferencesSettings.getWalletIndicatorVisibility();
      walletIndicatorVisibilitySB.getSelectables().forEach(selectable => {
        if (selectable.getModel() === value) {
          walletIndicatorVisibilitySB.setSelection([selectable]);
        }
      });
      walletIndicatorVisibilitySB.addListener("changeValue", e => {
        const selectable = e.getData();
        osparc.Preferences.patchPreferenceField("walletIndicatorVisibility", walletIndicatorVisibilitySB, selectable.getModel());
      });
      form.add(walletIndicatorVisibilitySB, this.tr("Show indicator"));

      const creditsWarningThresholdField = new qx.ui.form.Spinner().set({
        minimum: 50,
        maximum: 10000,
        singleStep: 10,
        allowGrowX: false
      });
      preferencesSettings.bind("creditsWarningThreshold", creditsWarningThresholdField, "value");
      creditsWarningThresholdField.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("creditsWarningThreshold", creditsWarningThresholdField, e.getData()));
      form.add(creditsWarningThresholdField, this.tr("Show warning when credits below"));

      box.add(new qx.ui.form.renderer.Single(form));

      this._add(box);
    },

    __addInactivitySetting: function() {
      const box = new osparc.widget.SectionBox(this.tr("Automatic Shutdown of Idle Instances"));

      const form = new qx.ui.form.Form();
      const inactivitySpinner = new qx.ui.form.Spinner().set({
        minimum: 1,
        maximum: 3*60, // 3 hours
        singleStep: 1,
        allowGrowX: false
      });
      const preferences = osparc.Preferences.getInstance();
      preferences.bind("userInactivityThreshold", inactivitySpinner, "value", {
        converter: value => Math.round(value / 60) // Stored in seconds, displayed in minutes
      });
      inactivitySpinner.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("userInactivityThreshold", inactivitySpinner, e.getData() * 60));
      form.add(inactivitySpinner, this.tr("Idle time before closing (in minutes)"));

      box.add(new qx.ui.form.renderer.Single(form));

      this._add(box);
    },

    __addLowDiskSpaceSetting: function() {
      const box = new osparc.widget.SectionBox(this.tr("Low Disk Space Threshold"));
      box.addHelper(this.tr("Set the warning Threshold for Low Disk Space availability"));

      const form = new qx.ui.form.Form();
      const diskUsageSpinner = new qx.ui.form.Spinner().set({
        minimum: 1,
        maximum: 10000,
        singleStep: 1,
        allowGrowX: false,
        enabled: true
      });
      const preferences = osparc.Preferences.getInstance();
      preferences.bind("lowDiskSpaceThreshold", diskUsageSpinner, "value");

      diskUsageSpinner.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("lowDiskSpaceThreshold", diskUsageSpinner, e.getData()));
      form.add(diskUsageSpinner, this.tr("Threshold (in GB)"));
      box.add(new qx.ui.form.renderer.Single(form));
      this._add(box);
    },

    refreshDefaultStudyTagsSetting: function() {
      if (this.isDisposed()) {
        return;
      }
      if (this.__defaultStudyTagsSaving) {
        this.__defaultStudyTagsRefreshPending = true;
        return;
      }
      const store = osparc.store.Tags.getInstance();
      if (!this.__defaultStudyTagsLoaded) {
        if (!this.__defaultStudyTagsLoad) {
          this.__defaultStudyTagsLoad = store.fetchTags()
            .then(() => {
              if (!this.isDisposed()) {
                this.__defaultStudyTagsLoaded = true;
                this.refreshDefaultStudyTagsSetting();
              }
            })
            .catch(err => console.error("Failed to load tags for default study settings", err))
            .finally(() => { this.__defaultStudyTagsLoad = null; });
        }
        return;
      }

      const box = this.__createDefaultStudyTagsSettingContent(store.getTags());
      if (this.__defaultStudyTagsBox) {
        this._remove(this.__defaultStudyTagsBox);
        this.__defaultStudyTagsBox.destroy();
      }
      this.__defaultStudyTagsBox = box;
      if (box) {
        this._addAt(box, Math.min(this.__defaultStudyTagsIndex, this._getChildren().length));
      }
    },

    __createDefaultStudyTagsSettingContent: function(tags) {
      if (!tags.length) {
        return null;
      }

      const box = new osparc.widget.SectionBox(this.tr("Default Study Tags"));
      box.addHelper(this.tr("Selected tags are automatically added to studies you create."));

      const preferences = osparc.Preferences.getInstance();
      const selectedTagIds = preferences.getDefaultStudyTagIds();
      const checkboxes = [];
      let isRestoring = false;
      const tagsList = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      tags.forEach(tag => {
        const tagId = tag.getTagId();
        const checkbox = new qx.ui.form.CheckBox(tag.getName()).set({
          value: selectedTagIds.includes(tagId)
        });
        checkboxes.push({
          checkbox,
          tagId
        });
        checkbox.addListener("changeValue", () => {
          if (isRestoring) {
            return;
          }
          const newTagIds = checkboxes
            .filter(item => item.checkbox.getValue())
            .map(item => item.tagId);
          const oldTagIds = preferences.getDefaultStudyTagIds();
          if (newTagIds.length === oldTagIds.length && newTagIds.every(tagId => oldTagIds.includes(tagId))) {
            return;
          }

          box.setEnabled(false);
          this.__defaultStudyTagsSaving = true;
          osparc.Preferences.patchPreference("defaultStudyTagIds", newTagIds)
            .then(() => preferences.setDefaultStudyTagIds(newTagIds))
            .catch(err => {
              osparc.FlashMessenger.logError(err);
              if (!this.isDisposed()) {
                isRestoring = true;
                checkboxes.forEach(item => item.checkbox.setValue(oldTagIds.includes(item.tagId)));
                isRestoring = false;
              }
            })
            .finally(() => {
              this.__defaultStudyTagsSaving = false;
              if (!this.isDisposed()) {
                box.setEnabled(true);
                if (this.__defaultStudyTagsRefreshPending) {
                  this.__defaultStudyTagsRefreshPending = false;
                  this.refreshDefaultStudyTagsSetting();
                }
              }
            });
        });
        tagsList.add(checkbox);
      });

      const scroll = new qx.ui.container.Scroll(tagsList).set({
        height: Math.min(tagsList.getSizeHint().height, 240)
      });
      box.add(scroll);
      return box;
    },

    __addS4LUserPrivacySettings: function() {
      const box = new osparc.widget.SectionBox(this.tr("Privacy Settings"));
      box.addHelper(this.tr("Help us improve Sim4Life user experience"));

      const preferencesSettings = osparc.Preferences.getInstance();

      const cbAllowMetricsCollection = new qx.ui.form.CheckBox(this.tr("Share usage data"));
      preferencesSettings.bind("allowMetricsCollection", cbAllowMetricsCollection, "value");
      cbAllowMetricsCollection.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("allowMetricsCollection", cbAllowMetricsCollection, e.getData()));
      box.add(cbAllowMetricsCollection);

      this._add(box);
    }
  }
});
