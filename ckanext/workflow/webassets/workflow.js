  jQuery(document).ready(function() {
    jQuery('#field-parent option[value=""]').remove();
    jQuery("#field-parent").val($("#field-parent option:first").val());
  });