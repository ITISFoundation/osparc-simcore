
/**
 *
 */
qx.Class.define("qxapp.test.Utils", {
  extend: qx.dev.unit.TestCase,


  members:
    {
      /*
      ---------------------- -----------------------------------------------------
        TESTS
      ---------------------------------------------------------------------------
      */

      testEncDecoding: function() {
        var got = qx.util.Base64.decode(qx.util.Base64.encode("foo:bar")).split(":");
        this.assertIdentical(got[0], "foo");
        this.assertIdentical(got[1], "bar");

        got = qx.util.Base64.decode(qx.util.Base64.encode("foo:")).split(":");
        this.assertIdentical(got[0], "foo");
        this.assertIdentical(got[1], "");

        got = qx.util.Base64.decode(qx.util.Base64.encode("foo:" + null)).split(":");
        this.assertIdentical(got[0], "foo");
        this.assertIdentical(got[1], "null");
      }

    }
});
