/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global intlTelInput */

/**
 * @ignore(intlTelInput)
 */

qx.Class.define("osparc.ui.form.IntlTelInput", {
  extend: qx.ui.core.Widget,
  implement: [qx.ui.form.IForm, qx.ui.form.IStringForm],
  include: [qx.ui.form.MForm, qx.ui.form.MModelProperty],

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.getContentElement().setStyles({
      "overflow": "visible" // needed for countries dropdown menu
    });

    const randId = Math.floor(Math.random() * 100);
    this.__htmlId = `phone-${randId}`;
    const html = `<input type='tel' id='${this.__htmlId}' name='phone' autocomplete='off'>`;
    const phoneNumber = this.getChildControl("phone-input-field");
    phoneNumber.setHtml(html);
    phoneNumber.addListenerOnce("appear", () => this.__convertInputToPhoneInput(), this);

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => this.__updateStyle());
  },

  properties: {
    // Form-compatible property
    value: {
      check: "String",
      nullable: true,
      event: "changeValue",
      apply: "_applyValue"
    },

    compactField: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "__updateStyle",
    }
  },

  members: {
    __htmlId: null,
    __itiInput: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "phone-input-field":
          control = new qx.ui.embed.Html();
          this._add(control, { flex: 1 });
          break;
        case "feedback-icon":
          control = new qx.ui.basic.Image();
          control.exclude();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    // IStringForm interface implementation
    getValue: function() {
      return this.__itiInput ? this.__itiInput.getNumber() : null;
    },

    setValue: function(value) {
      if (this.__itiInput && value) {
        // intlTelInput doesn't have a full setter for raw numbers
        this.__itiInput.setNumber(value);
      }
      this._applyValue(value);
    },

    resetValue: function() {
      this.setValue(null);
    },
    // IStringForm interface implementation

    _applyValue: function(value) {
      this.fireDataEvent("changeValue", value);
    },

    isValidNumber: function() {
      return this.__itiInput ? this.__itiInput.isValidNumber() : false;
    },

    verifyPhoneNumber: function() {
      const feedbackIcon = this.getChildControl("feedback-icon");
      feedbackIcon.show();
      const isValid = this.isValidNumber();
      feedbackIcon.set({
        toolTipText: "E.164: " + this.getValue(),
        source: isValid ? "@FontAwesome5Solid/check/16" : "@FontAwesome5Solid/exclamation-triangle/16",
        textColor: isValid ? "text" : "failed-red",
        alignY: "middle",
      });
      if (!isValid) {
        const validationError = this.__itiInput.getValidationError();
        const errorMap = {
          0: this.tr("Invalid number"),
          1: this.tr("Invalid country code"),
          2: this.tr("Number too short"),
          3: this.tr("Number too long")
        };
        const errorMsg = errorMap[validationError] || "Invalid number";
        feedbackIcon.set({
          toolTipText: errorMsg + ". " + feedbackIcon.getToolTipText()
        });
      }
      this.__updateStyle();
    },

    __updateStyle: function() {
      const phoneNumber = this.getChildControl("phone-input-field");
      const itiInput = this.__itiInput;
      const feedbackIcon = this.getChildControl("feedback-icon");
      const isCompact = this.isCompactField();

      const textColor = qx.theme.manager.Color.getInstance().resolve("text");
      const bgColor = qx.theme.manager.Color.getInstance().resolve("input_background");
      const height = isCompact ? 23 : 25;

      if (isCompact) {
        phoneNumber.set({
          margin: 0,
          marginLeft: -1,
        });
      } else {
        phoneNumber.set({
          marginTop: 2,
          marginLeft: 2,
          marginRight: 2,
        })
      }
      phoneNumber.set({
        minWidth: 185,
        maxHeight: height,
      });

      if (itiInput) {
        itiInput.a.style["width"] = feedbackIcon.isVisible() ? "185px" : "215px";
        itiInput.a.style["height"] = height + "px";
        itiInput.a.style["borderWidth"] = "0px";
        itiInput.a.style["backgroundColor"] = isCompact ? "transparent" : bgColor;
        itiInput.a.style["color"] = textColor;
      }

      document.documentElement.style.setProperty('--country-list-dropdown-bg', bgColor);
      document.documentElement.style.setProperty('--country-list-dropdown-text', textColor);
    },

    __convertInputToPhoneInput: function() {
      const convertInputToPhoneInput = () => {
        const domElement = document.querySelector(`#${this.__htmlId}`);
        const phoneNumber = this.getChildControl("phone-input-field");
        this.__itiInput = this.__inputToPhoneInput(domElement);
        phoneNumber.getContentElement().setStyles({
          "overflow": "visible" // needed for countries dropdown menu
        });
        this.__updateStyle();
      };

      const intlTelInputLib = osparc.wrapper.IntlTelInput.getInstance();
      if (intlTelInputLib.getLibReady()) {
        convertInputToPhoneInput();
      } else {
        intlTelInputLib.addListenerOnce("changeLibReady", e => {
          if (e.getData()) {
            convertInputToPhoneInput();
          }
        });
      }
    },

    __inputToPhoneInput: function(input) {
      const iti = intlTelInput(input, {
        initialCountry: "auto",
        geoIpLookup: callback => {
          fetch("https://ipapi.co/json")
            .then(res => res.json())
            .then(data => callback(data.country_code))
            .catch(() => callback("ch"));
        },
        preferredCountries: [],
        dropdownContainer: document.body,
      });
      this.__updateStyle();
      return iti;
    }
  }
});
