import { Component, OnInit } from '@angular/core';
import { Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { trigger, state, style, transition, animate } from '@angular/animations';
import { addIcons } from 'ionicons';
import { cloudUploadOutline, imageOutline, trashOutline, addOutline, checkmarkOutline, closeOutline } from 'ionicons/icons';
// Removed invalid imports from 'ionicons/icons'.
import { firstValueFrom } from 'rxjs';
import { ApiService, CompetitionPayload } from '../api.service';
import { AuthService } from '../services/auth.service';
import {
  IonHeader,
  IonToolbar,
  IonButtons,
  IonBackButton,
  IonTitle,
  IonContent,
  IonInput,
  IonSelect,
  IonSelectOption,
  IonIcon,
  IonCheckbox,
  IonTextarea,
} from '@ionic/angular/standalone';

interface Rule {
  name: string;
  description: string;
}

interface ScoringCategory {
  name: string;
  description: string;
  points: number;
}

interface Participant {
  id?: string;
  competition_id?: string;
  name: string;
  description: string;
  picture_location: string;
}

interface PointAccumulation {
  win: number;
  lose: number;
  draw: number;
}

interface Competition {
  id?: string;
  name: string;
  author: string;
  date_created?: string;
  logo_location: string;
  is_private: boolean;
  type: string;
  rules: Rule[];
  scoring_categories: ScoringCategory[];
  point_accumulation: PointAccumulation;
  participants: Participant[];
  fixtures: any[];
  league_table: any[];
  posts: any[];
  photos: any[];
  videos: any[];
}

@Component({
  selector: 'app-create-competition',
  templateUrl: './create-competition.page.html',
  styleUrls: ['./create-competition.page.scss'],
  standalone: true,
  animations: [
    trigger('slideInOut', [
      state('in', style({ height: '*', opacity: 1 })),
      state('out', style({ height: '0px', opacity: 0 })),
      transition('in <=> out', animate('300ms ease-in-out'))
    ]),
    trigger('fadeInUp', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(20px)' }),
        animate('300ms ease-out', style({ opacity: 1, transform: 'translateY(0)' }))
      ])
    ])
  ],
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    IonHeader,
    IonToolbar,
    IonButtons,
    IonBackButton,
    IonTitle,
    IonContent,
    IonInput,
    IonSelect,
    IonSelectOption,
    IonIcon,
    IonCheckbox,
    IonTextarea,
  ],
})
export class CreateCompetitionPage implements OnInit {
  activeSection: string = 'basic';
  logoFile: File | null = null;
  logoPreview: string = '';
  isUploadingLogo = false;
  competition: Competition = {
    name: '',
    author: '',
    logo_location: '',
    is_private: false,
    type: '',
    rules: [],
    scoring_categories: [],
    point_accumulation: {
      win: 3,
      lose: 0,
      draw: 1
    },
    participants: [],
    fixtures: [],
    league_table: [],
    posts: [],
    photos: [],
    videos: []
  };

  isSubmitting = false;

  constructor(
    private apiService: ApiService,
    private auth: AuthService,
    private router: Router
  ) {
    addIcons({imageOutline,cloudUploadOutline,trashOutline,addOutline,checkmarkOutline,closeOutline});
  }

  ngOnInit() {
    // Initialize with default rule and scoring category
    this.addRule();
    this.addScoringCategory();
    this.addParticipant();
  }

  setActiveSection(section: string) {
    this.activeSection = this.activeSection === section ? '' : section;
  }
  addRule() {
    this.competition.rules.push({
      name: '',
      description: ''
    });
  }

  removeRule(index: number) {
    this.competition.rules.splice(index, 1);
  }

  addScoringCategory() {
    this.competition.scoring_categories.push({
      name: '',
      description: '',
      points: 0
    });
  }

  removeScoringCategory(index: number) {
    this.competition.scoring_categories.splice(index, 1);
  }

  addParticipant() {
    this.competition.participants.push({
      name: '',
      description: '',
      picture_location: ''
    });
  }

  removeParticipant(index: number) {
    this.competition.participants.splice(index, 1);
  }

  // Logo upload functionality
  onLogoFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    
    if (file) {
      this.processLogoFile(file);
    }
    
    // Reset input value to allow selecting the same file again
    input.value = '';
  }

  onLogoDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    
    const files = Array.from(event.dataTransfer?.files || []);
    const imageFile = files.find(file => file.type.startsWith('image/'));
    
    if (imageFile) {
      this.processLogoFile(imageFile);
    }
  }

  onLogoDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
  }

  onLogoDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
  }

  private processLogoFile(file: File) {
    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file (JPG, PNG, GIF, etc.)');
      return;
    }

    // Validate file size (5MB limit)
    const maxSize = 5 * 1024 * 1024; // 5MB
    if (file.size > maxSize) {
      alert('Image file is too large. Please select an image smaller than 5MB.');
      return;
    }

    this.logoFile = file;
    
    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      this.logoPreview = e.target?.result as string;
    };
    reader.readAsDataURL(file);
  }

  removeLogo() {
    this.logoFile = null;
    this.logoPreview = '';
    this.competition.logo_location = '';
  }

  private async uploadLogo(): Promise<string> {
    if (!this.logoFile) return '';

    this.isUploadingLogo = true;
    
    try {
      // Simulate logo upload - replace with actual upload logic
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // In a real implementation, you would upload to your server/cloud storage
      // and return the URL. For now, we'll use the preview URL
      return this.logoPreview;
      
    } catch (error) {
      console.error('Logo upload failed:', error);
      throw new Error('Failed to upload logo');
    } finally {
      this.isUploadingLogo = false;
    }
  }
  async onSubmit() {
    if (this.isSubmitting) return;

    const user = this.auth.getCurrentUser();
    if (!user) {
      alert('Please log in to create a competition.');
      await this.router.navigate(['/auth/login']);
      return;
    }

    if (!this.competition.name.trim()) {
      alert('Please enter a competition name.');
      return;
    }

    if (!this.competition.type.trim()) {
      alert('Please select a competition type.');
      return;
    }

    this.isSubmitting = true;

    try {
      if (this.logoFile) {
        this.competition.logo_location = await this.uploadLogo();
      }

      const userName = user.name || user.email || 'Unknown User';
      const ownerId = this.auth.getOwnerId();

      const participantNames = this.competition.participants
        .map((p) => p.name.trim())
        .filter((name) => name !== '');

      if (!participantNames.includes(userName)) {
        participantNames.unshift(userName);
      }

      const payload: CompetitionPayload = {
        id: crypto.randomUUID(),
        name: this.competition.name.trim(),
        author: userName,
        owner_id: ownerId,
        date_created: new Date().toISOString(),
        logo_location: this.competition.logo_location || '',
        is_private: this.competition.is_private,
        type: this.competition.type,
        rules: this.competition.rules.filter(
          (rule) => rule.name.trim() !== '' || rule.description.trim() !== ''
        ),
        scoring_categories: this.competition.scoring_categories.filter(
          (category) => category.name.trim() !== ''
        ),
        point_accumulation: { ...this.competition.point_accumulation },
        participants: participantNames,
        fixtures: [],
        league_table: [],
        posts: [],
        photos: [],
        videos: [],
      };

      await firstValueFrom(this.apiService.createCompetition(payload));

      alert('Competition created successfully!');
      await this.router.navigate(['/home']);
    } catch (error) {
      console.error('Error creating competition:', error);
      alert('Failed to create competition. Please try again.');
    } finally {
      this.isSubmitting = false;
    }
  }
}