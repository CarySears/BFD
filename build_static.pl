#!/usr/bin/env perl
use strict;
use warnings;
use utf8;

sub read_file {
  my ($path) = @_;
  open(my $fh, "<:raw", $path) or die "Failed to read $path: $!";
  local $/ = undef;
  my $content = <$fh>;
  close($fh);
  return $content;
}

sub write_file {
  my ($path, $content) = @_;
  open(my $fh, ">:raw", $path) or die "Failed to write $path: $!";
  print {$fh} $content;
  close($fh);
}

my $source_path = "/workspace/_source.html";
my $out_path    = "/workspace/index.html";

my $html = read_file($source_path);

# Strip WP Rocket/IE helper scripts (very large; not needed for static snapshot)
$html =~ s|<script>if\(navigator\.userAgent\.match\(/MSIE.*?</script>||gis;
$html =~ s|<script>\(\(\)=>\{class RocketLazyLoadScripts.*?</script>||gis;

# Strip common analytics blocks to avoid noisy network calls
$html =~ s|<!-- Google Tag Manager -->.*?<!-- End Google Tag Manager -->||gis;
$html =~ s|<!-- Google Tag Manager \(noscript\) -->.*?<!-- End Google Tag Manager \(noscript\) -->||gis;
$html =~ s|<!-- Meta Pixel Code -->.*?<!-- End Meta Pixel Code -->||gis;

# Strip UserWay widget
$html =~ s|<script[^>]+cdn\.userway\.org/widget\.js[^>]*></script>||gis;

# Strip CleanTalk spam protection assets
$html =~ s|<script[^>]+cleantalk[^>]*></script>||gis;
$html =~ s|<script[^>]+apbct-public-bundle_full-protection[^>]*></script>||gis;
$html =~ s|<script[^>]*>\s*var\s+ctPublicFunctions\b.*?</script>||gis;
$html =~ s|<script[^>]*>\s*var\s+ctPublic\s*=\s*\{.*?</script>||gis;

# Convert rocket-delayed script tags into normal script tags
$html =~ s/\btype="rocketlazyloadscript"\b//gi;
$html =~ s/\sdata-rocket-src=/ src=/gi;
$html =~ s/\sdata-rocket-[a-zA-Z0-9_-]+="[^"]*"//g;
$html =~ s/\sdata-minify="[^"]*"//g;
$html =~ s/\sdata-wp-strategy="[^"]*"//g;

# Ensure a <base> tag so relative URLs keep working (WordPress content uses /wp-content/... etc)
if ( $html !~ /<base\s+href=/i ) {
  $html =~ s|<head>|<head>\n<base href="https://www.bronxvillefamilydental.com/">|i;
}

# Add a small runtime:
# - de-lazify images/picture sources (WP Rocket uses data-lazy-*)
# - basic mobile nav toggle + submenu toggles (enough for local preview)
my $shim = <<'JS';
<script>
(function(){
  function delazify(){
    document.querySelectorAll('img[data-lazy-src]').forEach(function(img){
      var lazy = img.getAttribute('data-lazy-src');
      if(!lazy) return;
      var cur = img.getAttribute('src') || '';
      if(!cur || cur.indexOf('data:image') === 0) img.setAttribute('src', lazy);
      img.removeAttribute('data-lazy-src');
    });
    document.querySelectorAll('source[data-lazy-srcset]').forEach(function(source){
      var lazy = source.getAttribute('data-lazy-srcset');
      if(!lazy) return;
      source.setAttribute('srcset', lazy);
      source.removeAttribute('data-lazy-srcset');
    });
  }

  function setupNav(){
    var opener = document.querySelector('.menu-opener');
    if(opener){
      opener.addEventListener('click', function(e){
        e.preventDefault();
        document.body.classList.toggle('nav-open');
      });
    }

    document.querySelectorAll('#nav .opener').forEach(function(span){
      span.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var li = span.closest('li');
        if(li) li.classList.toggle('open');
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    delazify();
    setupNav();
  });
})();
</script>
JS

$html =~ s|</body>|$shim\n</body>|i;

write_file($out_path, $html);

print "Wrote $out_path\n";
