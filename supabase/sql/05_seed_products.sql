-- STEP 5: add 26 demo products to the Nestora catalog.
-- Each gets 1000 units of stock and a random whole-rupee price between 500 and 12000.
-- Replace PASTE-YOUR-ADMIN-USER-ID with your own user UUID (the id from GET /api/auth/me,
-- or Supabase > Authentication > Users). Safe to re-run: existing SKUs are skipped.
-- Stock is added through admin_add_stock so every unit has an inventory_movements row.
do $$
declare
  v_admin uuid := 'PASTE-YOUR-ADMIN-USER-ID';
  r record;
  v_id uuid;
begin
  for r in
    select * from (values
      -- Kitchen
      ('NK-700', 'Nestora Brew Glass Kettle NK-700', '1.7 L borosilicate glass kettle with LED ring, auto shut-off and boil-dry protection.'),
      ('CM-210', 'Nestora Brew Pour-Over Coffee Maker CM-210', 'Drip coffee maker for 1-6 cups with reusable steel filter and warming plate.'),
      ('FP-120', 'Nestora Brew French Press FP-120', '1 L French press with double steel mesh filter and heat-resistant glass.'),
      ('MF-330', 'Nestora Brew Milk Frother MF-330', 'Rechargeable handheld milk frother with stand. Charges over USB-C.'),
      ('TS-410', 'Nestora Toaster TS-410', 'Two-slice toaster with 7 browning levels, defrost, reheat and crumb tray.'),
      ('AF-550', 'Nestora Air Fryer AF-550', '4.5 L air fryer with 8 presets, timer up to 60 minutes and non-stick basket.'),
      ('BL-300', 'Nestora Personal Blender BL-300', '350 W blender with two 600 ml travel bottles for smoothies and shakes.'),
      ('SC-150', 'Nestora Kitchen Scale SC-150', 'Digital kitchen scale up to 5 kg with tare function and 1 g precision.'),
      ('KN-800', 'Nestora Chef Knife KN-800', '8-inch stainless steel chef knife with full-tang handle.'),
      ('CB-220', 'Nestora Bamboo Chopping Board CB-220', 'Large bamboo chopping board with juice groove and side handles.'),
      ('SJ-600', 'Nestora Spice Jar Set SJ-600', 'Set of 6 glass spice jars with airtight bamboo lids and labels.'),
      ('IB-750', 'Nestora Insulated Bottle IB-750', '750 ml stainless steel bottle. Keeps drinks cold 24 hours or hot 12 hours.'),
      -- Smart home
      ('PL-010', 'Nestora Smart Plug PL-010', 'Wi-Fi smart plug with app control, schedules and energy monitoring.'),
      ('SB-002', 'Nestora Brew Smart Bulb SB-002', 'Colour smart bulb, 9 W, 16 million colours, works with the Nestora app.'),
      ('LS-100', 'Nestora Smart LED Strip LS-100', '5 m colour LED strip with app control and music sync.'),
      ('MS-050', 'Nestora Motion Sensor MS-050', 'Battery motion sensor that triggers smart bulbs and plugs.'),
      ('DB-090', 'Nestora Video Doorbell DB-090', '1080p video doorbell with two-way audio, night vision and motion alerts.'),
      ('TM-500', 'Nestora Smart Thermometer TM-500', 'Indoor temperature and humidity sensor with app history.'),
      -- Lighting
      ('DL-200', 'Nestora Desk Lamp DL-200', 'Dimmable LED desk lamp with 3 colour temperatures and USB charging port.'),
      ('NL-020', 'Nestora Night Light NL-020', 'Plug-in night light that turns on with motion in the dark.'),
      -- Air and cleaning
      ('AP-700', 'Nestora Air Purifier AP-700', 'HEPA air purifier for rooms up to 30 square metres, with sleep mode.'),
      ('HU-300', 'Nestora Ultrasonic Humidifier HU-300', '3 L cool-mist humidifier, quiet operation and auto shut-off when empty.'),
      ('VC-900', 'Nestora Cordless Vacuum VC-900', 'Cordless stick vacuum with up to 40 minutes runtime and wall mount.'),
      ('FN-400', 'Nestora Tower Fan FN-400', 'Tower fan with 3 speeds, oscillation, remote and 8-hour timer.'),
      -- Bed and bath
      ('TW-100', 'Nestora Cotton Bath Towel Set TW-100', 'Set of 2 soft cotton bath towels, 70 x 140 cm.'),
      ('CD-050', 'Nestora Soy Wax Candle CD-050', 'Hand-poured soy wax candle, about 40 hours burn time.')
    ) as t(sku, name, description)
  loop
    if exists (select 1 from public.products where sku = r.sku) then
      continue;
    end if;

    insert into public.products (sku, name, description, price, is_active)
    values (r.sku, r.name, r.description, round((500 + random() * 11500)::numeric, 0), true)
    returning id into v_id;

    perform public.admin_add_stock(v_id, 1000, v_admin, 'Initial demo stock');
  end loop;
end $$;

-- Check the result (read-only).
select sku, name, price, stock_quantity, is_active
from public.products
order by name;
