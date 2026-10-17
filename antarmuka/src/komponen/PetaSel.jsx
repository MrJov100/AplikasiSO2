import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { angka } from '../api.js'

// Peta sebaran kesepuluh sel grid pada halaman Informasi Lokasi.
// Yang digambar adalah TITIK pada koordinat permintaan (sama dengan tabel di
// bawahnya), bukan kotak sel. Simpul kisi yang dikembalikan Open-Meteo bergeser
// 2-8 km dari titik ini dan resolusi asal CAMS 0,4 derajat, sehingga kotak
// berukuran berapa pun akan menyiratkan batas spasial yang tidak akurat.
// Fitur ini pelengkap tampilan; tidak menjadi bagian rancangan pada naskah.
export default function PetaSel({ data, admin }) {
  const batas = data.map((l) => [l.lintang, l.bujur])

  return (
    <MapContainer
      bounds={batas}
      boundsOptions={{ padding: [36, 36] }}
      scrollWheelZoom={false}
      className="peta-sel"
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={18}
      />
      {data.map((l) => (
        <CircleMarker
          key={l.kode_sel}
          center={[l.lintang, l.bujur]}
          radius={8}
          pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#16507a', fillOpacity: 0.9 }}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            <div className="peta-tip">
              <b>{admin ? `${l.kode_sel} · ${l.nama}` : l.nama}</b>
              <span>{l.wilayah_administratif}</span>
              <span>Elevasi {angka(l.elevasi, 0)} m</span>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
