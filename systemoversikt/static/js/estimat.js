$(function () {

  /* Functions */

  var loadForm = function () {
    var btn = $(this);
    $.ajax({
      url: btn.attr("data-url"),
      type: 'get',
      dataType: 'json',
      beforeSend: function () {
        $("#modal-estimat .modal-content").html("");
        $("#modal-estimat").modal("show");
      },
      success: function (data) {
        $("#modal-estimat .modal-content").html(data.html_form);
      }
    });
  };

  var saveForm = function () {
    var form = $(this);
    $.ajax({
      url: form.attr("action"),
      data: form.serialize(),
      type: form.attr("method"),
      dataType: 'json',
      success: function (data) {
        if (data.form_is_valid) {
          $("#estimat-table tbody").html(data.html_estimat_list);
          $("#modal-estimat").modal("hide");
        }
        else {
          $("#modal-estimat .modal-content").html(data.html_form);
        }
      }
    });
    return false;
  };


  /* Binding */

  // Create estimat
  $(".js-create-estimat").click(loadForm);
  $("#modal-estimat").on("submit", ".js-estimat-create-form", saveForm);

  // Update estimat
  $("#estimat-table").on("click", ".js-update-estimat", loadForm);
  $("#modal-estimat").on("submit", ".js-estimat-update-form", saveForm);

  // Delete estimat
  $("#estimat-table").on("click", ".js-delete-estimat", loadForm);
  $("#modal-estimat").on("submit", ".js-estimat-delete-form", saveForm);

});
