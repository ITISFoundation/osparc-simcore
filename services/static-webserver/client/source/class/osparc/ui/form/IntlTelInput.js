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

    this.setFocusable(true);

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
    __inputElement: null,
    __phoneInput: null,

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
      return this.__phoneInput ? this.__phoneInput.getNumber() : null;
    },

    setValue: function(value) {
      if (this.__phoneInput && value) {
        // intlTelInput doesn't have a full setter for raw numbers
        this.__phoneInput.setNumber(value);
      }
      this._applyValue(value);
    },

    resetValue: function() {
      this.setValue(null);
    },
    // IStringForm interface implementation

    // Make the widget tabbable/focusable
    focus: function() {
      if (this.__inputElement) {
        this.__inputElement.focus();
      } else {
        // fallback: let qooxdoo focus the content element
        this.base(arguments);
      }
    },

    tabFocus: function() {
      this.focus();
    },

    getFocusElement: function() {
      const phoneNumber = this.getChildControl("phone-input-field");
      // phoneNumber is a qx.ui.embed.Html → it has a ContentElement (qx.html.Element)
      return phoneNumber.getContentElement();
    },
    // Make the widget tabbable/focusable

    _applyValue: function(value) {
      this.fireDataEvent("changeValue", value);
    },

    validate: function() {
      return this.isValidNumber();
    },

    isValidNumber: function() {
      return this.__phoneInput ? this.__phoneInput.isValidNumber() : false;
    },

    verifyPhoneNumber: function() {
      const value = this.getValue();
      const feedbackIcon = this.getChildControl("feedback-icon");
      feedbackIcon.setVisibility(value ? "visible" : "excluded");
      const isValid = this.isValidNumber();
      feedbackIcon.set({
        toolTipText: "E.164: " + this.getValue(),
        source: isValid ? "@FontAwesome5Solid/check/16" : "@FontAwesome5Solid/exclamation-triangle/16",
        textColor: isValid ? "text" : "failed-red",
        alignY: "middle",
      });
      if (!isValid) {
        const validationError = this.__phoneInput.getValidationError();
        const errorMap = {
          0: this.tr("Invalid number"),
          1: this.tr("Invalid country code"),
          2: this.tr("Number too short"),
          3: this.tr("Number too long")
        };
        const errorMsg = errorMap[validationError] || this.tr("Invalid number");
        feedbackIcon.set({
          toolTipText: errorMsg + ". " + feedbackIcon.getToolTipText()
        });
      }
      this.__updateStyle();
    },

    __updateStyle: function() {
      const isCompact = this.isCompactField();
      const textColor = qx.theme.manager.Color.getInstance().resolve("text");
      const bgColor = qx.theme.manager.Color.getInstance().resolve("input_background");
      const productColor = qx.theme.manager.Color.getInstance().resolve("product-color");
      const phoneInputField = this.getChildControl("phone-input-field");
      const feedbackIcon = this.getChildControl("feedback-icon");
      const width = isCompact ? 152 : 215;
      const phoneInputWidth = feedbackIcon.isVisible() ? width - 14 : width;
      const height = isCompact ? 26 : 30;

      phoneInputField.set({
        maxWidth: width,
        maxHeight: height,
        margin: 0,
      });

      const phoneInput = this.__phoneInput;
      if (phoneInput) {
        phoneInput.a.style["width"] = phoneInputWidth + "px";
        phoneInput.a.style["height"] = height + "px";
        phoneInput.a.style["borderWidth"] = "0px";
        phoneInput.a.style["backgroundColor"] = isCompact ? "transparent" : bgColor;
        phoneInput.a.style["color"] = textColor;
      }

      document.documentElement.style.setProperty('--country-list-dropdown-bg', bgColor);
      document.documentElement.style.setProperty('--country-list-dropdown-text', textColor);
      document.documentElement.style.setProperty('--border-bottom-color-focused', productColor);
    },

    __convertInputToPhoneInput: function() {
      const convertInputToPhoneInput = () => {
        const domElement = document.querySelector(`#${this.__htmlId}`);
        this.__inputElementToPhoneInput(domElement);
        const phoneNumber = this.getChildControl("phone-input-field");
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

    __inputElementToPhoneInput: function(domElement) {
      this.__inputElement = domElement; // keep reference to raw <input>
      this.__phoneInput = intlTelInput(domElement, {
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

      // Trigger validation on blur
      domElement.addEventListener("blur", () => this.verifyPhoneNumber());

      this.__updateStyle();
    }
  }
});
