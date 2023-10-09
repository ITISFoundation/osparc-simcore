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

qx.Class.define("osparc.widget.IntlTelInput", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    this.getContentElement().setStyles({
      "overflow": "visible" // needed for countries dropdown menu
    });

    const randId = Math.floor(Math.random() * 100);
    const html = `<input type='tel' id='phone-${randId}' name='phone' autocomplete='off'>`;
    const phoneNumber = new qx.ui.embed.Html(html).set({
      marginTop: 2,
      marginLeft: 2,
      marginRight: 2,
      minWidth: 185,
      maxHeight: 25
    });
    this._add(phoneNumber);
    phoneNumber.addListenerOnce("appear", () => {
      const convertInputToPhoneInput = () => {
        const domElement = document.querySelector(`#phone-${randId}`);
        this.__itiInput = this.__inputToPhoneInput(domElement);
        phoneNumber.getContentElement().setStyles({
          "overflow": "visible" // needed for countries dropdown menu
        });
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
    });

    const feedbackCheck = this.__feedbackCheck = new qx.ui.basic.Image().set({
      paddingTop: 3
    });
    feedbackCheck.exclude();
    this._add(feedbackCheck);
  },

  statics: {
    updateStyle: function(itiInput, checkIcon) {
      itiInput.a.style["width"] = checkIcon && checkIcon.isVisible() ? "185px" : "215px";
      itiInput.a.style["height"] = "23px";
      itiInput.a.style["borderWidth"] = "0px";
      itiInput.a.style["backgroundColor"] = qx.theme.manager.Meta.getInstance().getTheme().name.includes("Light") ? "#eaedef" : "#202426";
      itiInput.a.style["color"] = qx.theme.manager.Color.getInstance().resolve("text");
    }
  },

  members: {
    __itiInput: null,
    __feedbackCheck: null,

    getNumber: function() {
      return this.__itiInput.getNumber();
    },

    isValidNumber: function() {
      return this.__itiInput.isValidNumber();
    },

    verifyPhoneNumber: function() {
      const isValid = this.isValidNumber();
      this.__feedbackCheck.set({
        toolTipText: "E.164: " + this.getNumber(),
        source: isValid ? "@FontAwesome5Solid/check/18" : "@FontAwesome5Solid/exclamation-triangle/18",
        textColor: isValid ? "text" : "failed-red"
      });
      this.__feedbackCheck.show();
      if (!isValid) {
        const validationError = this.__itiInput.getValidationError();
        const errorMap = {
          0: this.tr("Invalid number"),
          1: this.tr("Invalid country code"),
          2: this.tr("Number too short"),
          3: this.tr("Number too long")
        };
        const errorMsg = validationError in errorMap ? errorMap[validationError] : "Invalid number";
        this.__feedbackCheck.set({
          toolTipText: errorMsg + ". " + this.__feedbackCheck.getToolTipText()
        });
      }
      this.self().updateStyle(this.__itiInput, this.__feedbackCheck);
    },

    __inputToPhoneInput: function(input) {
      const iti = intlTelInput(input, {
        initialCountry: "ch", // auto: geoIpLookup. need to unlock https://ipinfo.io/,
        preferredCountries: ["ch", "us"]
      });
      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => this.self().updateStyle(iti));
      this.self().updateStyle(iti);
      return iti;
    }
  }
});
