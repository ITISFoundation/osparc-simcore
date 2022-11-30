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
 * @asset(intl-tel-input/js/intlTelInput.min.js)
 * @asset(intl-tel-input/js/data.min.js)
 * @asset(intl-tel-input/js/utils.js)
 * @asset(intl-tel-input/css/intlTelInput.min.css)
 * @asset(intl-tel-input/img/flags.png)
 * @asset(intl-tel-input/img/flags@2x.png)
 * @ignore(intlTelInput)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/jackocnr/intl-tel-input' target='_blank'>IntlTelInput</a>
 */

qx.Class.define("osparc.wrapper.IntlTelInput", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "intlTelInput",
    VERSION: "17.0.19",
    URL: "https://github.com/jackocnr/intl-tel-input"
  },

  construct: function() {
    this.base(arguments);
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  members: {
    init: function() {
      // initialize the script loading
      let intlTelInputPath = "intl-tel-input/js/intlTelInput.min.js";
      let dataPath = "intl-tel-input/js/data.min.js";
      let utilsPath = "intl-tel-input/js/utils.js";
      let intlTelInputCss = "intl-tel-input/css/intlTelInput.min.css";
      let intlTelInputCssUri = qx.util.ResourceManager.getInstance().toUri(intlTelInputCss);
      qx.module.Css.includeStylesheet(intlTelInputCssUri);
      let dynLoader = new qx.util.DynamicScriptLoader([
        intlTelInputPath,
        dataPath,
        utilsPath
      ]);

      dynLoader.addListenerOnce("ready", () => {
        console.log(intlTelInputPath + " loaded");
        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    inputToPhoneInput: function(input) {
      const iti = intlTelInput(input, {
        initialCountry: "ch", // auto: geoIpLookup. need to unlock https://ipinfo.io/
        separateDialCode: true
      });
      return iti;
    }
  }
});
